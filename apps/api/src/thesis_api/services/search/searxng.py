"""SearXNG adapter: canary, normalize, in-process cache, degrade detection.

Caching keyed by firm + normalized query (tenant_private). Inspired by agent-search
cache-key discipline (MIT) — reimplemented for Thesis contracts.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

import httpx

from thesis_api.services.search.normalize import canonicalize_url, dedupe_results_by_url

SearchState = Literal["ok", "degraded", "unavailable"]

# Process-wide adapter so cross-domain / deep-pass queries share TTL cache.
_SHARED: SearxngAdapter | None = None
_SHARED_URL: str | None = None


def shared_searxng_adapter(base_url: str, *, timeout_s: float = 25.0) -> SearxngAdapter:
    """Reuse one adapter per worker process (cache survives across domains)."""
    global _SHARED, _SHARED_URL
    url = (base_url or "").rstrip("/")
    if _SHARED is None or _SHARED_URL != url:
        _SHARED = SearxngAdapter(url, timeout_s=timeout_s, min_ok_results=1)
        _SHARED_URL = url
    return _SHARED


@dataclass
class SearchHealth:
    state: SearchState
    json_enabled: bool
    result_count: int
    engines_responding: list[str] = field(default_factory=list)
    engines_failed: list[str] = field(default_factory=list)
    from_cache: bool = False
    last_canary_at: str | None = None
    error: str | None = None


@dataclass
class _CacheEntry:
    expires_at: float
    payload: dict[str, Any]


class SearxngAdapter:
    def __init__(
        self,
        base_url: str,
        *,
        ttl_general_s: int = 6 * 3600,
        ttl_news_s: int = 3600,
        min_ok_results: int = 3,
        timeout_s: float = 20.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.ttl_general_s = ttl_general_s
        self.ttl_news_s = ttl_news_s
        self.min_ok_results = min_ok_results
        self.timeout_s = timeout_s
        self._cache: dict[str, _CacheEntry] = {}
        self._client: httpx.AsyncClient | None = None

    async def _http(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout_s)
        return self._client

    def cache_key(
        self,
        *,
        firm_id: str,
        query: str,
        category: str,
        language: str | None,
        time_range: str | None,
        page: int,
    ) -> str:
        blob = "|".join(
            [
                firm_id,
                "searxng",
                query.strip().lower(),
                category,
                language or "",
                time_range or "",
                str(page),
            ]
        )
        return hashlib.sha256(blob.encode()).hexdigest()

    async def search(
        self,
        *,
        firm_id: str,
        query: str,
        category: str = "general",
        language: str | None = None,
        time_range: str | None = None,
        page: int = 1,
        max_results: int = 20,
    ) -> dict[str, Any]:
        key = self.cache_key(
            firm_id=firm_id,
            query=query,
            category=category,
            language=language,
            time_range=time_range,
            page=page,
        )
        now = time.time()
        hit = self._cache.get(key)
        if hit and hit.expires_at > now:
            return {**hit.payload, "from_cache": True}

        params: dict[str, Any] = {"q": query, "format": "json", "pageno": page}
        if category:
            params["categories"] = category
        if language:
            params["language"] = language
        if time_range:
            params["time_range"] = time_range

        try:
            client = await self._http()
            r = await client.get(f"{self.base_url}/search", params=params)
            if r.status_code == 403:
                return self._unavailable("json_format_forbidden", json_enabled=False)
            r.raise_for_status()
            data = r.json()
        except Exception as exc:  # noqa: BLE001
            return self._unavailable(str(exc), json_enabled=False)

        raw_results = data.get("results") or []
        normalized = []
        for i, item in enumerate(raw_results[:max_results]):
            url = str(item.get("url") or "")
            if not url.startswith("http"):
                continue
            normalized.append(
                {
                    "title": item.get("title") or "",
                    "url": url,
                    "canonical_url": canonicalize_url(url),
                    "snippet": item.get("content"),
                    "engine": item.get("engine"),
                    "position": i + 1,
                    "category": category,
                }
            )
        normalized = dedupe_results_by_url(normalized)
        engines = sorted({str(x.get("engine")) for x in normalized if x.get("engine")})
        unresponsive = data.get("unresponsive_engines") or []
        failed = [str(x[0] if isinstance(x, (list, tuple)) else x) for x in unresponsive]

        if len(normalized) == 0 and failed:
            state: SearchState = "degraded"
        elif len(normalized) < self.min_ok_results:
            state = "degraded"
        else:
            state = "ok"

        payload = {
            "state": state,
            "json_enabled": True,
            "results": normalized,
            "engines_responding": engines,
            "engines_failed": failed,
            "from_cache": False,
            "result_count": len(normalized),
            "last_canary_at": datetime.now(timezone.utc).isoformat(),
        }
        ttl = self.ttl_news_s if category == "news" else self.ttl_general_s
        self._cache[key] = _CacheEntry(expires_at=now + ttl, payload=payload)
        return payload

    async def canary(self, firm_id: str = "system") -> SearchHealth:
        """General canary; if degraded with zero hits, retry a Wikipedia-friendly query."""
        result = await self.search(
            firm_id=firm_id, query="open source software", category="general", max_results=10
        )
        if result.get("result_count", 0) == 0 and result.get("state") != "unavailable":
            # Narrower query often still returns via wikipedia when aggregators are blocked.
            wiki = await self.search(
                firm_id=firm_id,
                query="Apache License",
                category="general",
                max_results=10,
            )
            if wiki.get("result_count", 0) > result.get("result_count", 0):
                result = {
                    **wiki,
                    "engines_failed": sorted(
                        set(result.get("engines_failed") or [])
                        | set(wiki.get("engines_failed") or [])
                    ),
                }
                if wiki.get("result_count", 0) >= 1 and wiki.get("state") == "degraded":
                    # Accept single-engine success as ok for readiness canary.
                    result = {**result, "state": "ok"}
        return SearchHealth(
            state=result["state"],
            json_enabled=result.get("json_enabled", False),
            result_count=result.get("result_count", 0),
            engines_responding=result.get("engines_responding", []),
            engines_failed=result.get("engines_failed", []),
            from_cache=result.get("from_cache", False),
            last_canary_at=result.get("last_canary_at"),
            error=result.get("error"),
        )

    def _unavailable(self, error: str, *, json_enabled: bool) -> dict[str, Any]:
        return {
            "state": "unavailable",
            "json_enabled": json_enabled,
            "results": [],
            "engines_responding": [],
            "engines_failed": [],
            "from_cache": False,
            "result_count": 0,
            "last_canary_at": None,
            "error": error,
        }
