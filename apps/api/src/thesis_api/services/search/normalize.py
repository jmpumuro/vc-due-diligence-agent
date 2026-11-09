"""URL / domain normalization for search dedup (patterns inspired by agent-search MIT)."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

_TRACKING = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "gclid",
    "fbclid",
    "mc_cid",
    "mc_eid",
}


def canonicalize_url(url: str) -> str:
    raw = (url or "").strip().rstrip("\\")
    if not raw:
        return ""
    parsed = urlparse(raw)
    scheme = (parsed.scheme or "https").lower()
    host = (parsed.hostname or "").lower().removeprefix("www.")
    path = parsed.path or "/"
    path = re.sub(r"/+", "/", path)
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    q = parse_qs(parsed.query, keep_blank_values=False)
    kept = {k: v for k, v in q.items() if k.lower() not in _TRACKING}
    query = urlencode(kept, doseq=True)
    return urlunparse((scheme, host, path, "", query, ""))


def registrable_domain(url_or_host: str) -> str:
    host = url_or_host.strip().lower()
    if "://" in host:
        host = urlparse(host).hostname or ""
    host = host.removeprefix("www.")
    parts = [p for p in host.split(".") if p]
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return host


def dedupe_results_by_url(results: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for r in results:
        key = canonicalize_url(str(r.get("url") or r.get("canonical_url") or ""))
        if not key or key in seen:
            continue
        seen.add(key)
        out.append({**r, "canonical_url": key, "domain": registrable_domain(key)})
    return out
