# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Thesis contributors
"""Stage 5 research helpers — SearXNG + SafeFetch + evidence + corroboration (public only)."""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from urllib.parse import quote_plus
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from thesis_contracts.base import DomainId
from thesis_contracts.grounding import ground_numeric_statement, trust_for_grounding
from thesis_contracts.public_fetch import PublicFetchRequest
from thesis_contracts.research import Claim, ContradictionRecord

from thesis_api.services.claims_store import insert_claim
from thesis_api.services.contradictions_store import insert_contradiction
from thesis_api.services.corroboration import SourceDocument, rank_and_corroborate
from thesis_api.services.evidence_store import insert_span, persist_fetch_evidence
from thesis_api.services.fetch.public_executor import execute_public_fetch
from thesis_api.services.fetch.safe_fetcher import SafeFetchError
from thesis_api.services.fetch.sandbox_executor import SandboxExecutionError
from thesis_api.services.search.normalize import canonicalize_url, registrable_domain
from thesis_api.services.search.searxng import shared_searxng_adapter
from thesis_api.services.source_quality import (
    REFERENCE_ONLY_DOMAINS,
    has_preferred_independent_source,
    identity_evidence_is_thin,
    passage_is_chrome,
    passage_usable_for_domain,
    source_rank_score,
    statement_admits_evidence_gap,
    url_looks_like_serp,
)
from thesis_api.settings import settings
from thesis_api.tenant import TenantContext

logger = logging.getLogger("thesis_screening_research")

# Firm-scoped fetch cache so parallel domains reuse company-site / news pages.
_FETCH_CACHE: dict[str, dict[str, Any]] = {}
_FETCH_CACHE_LOCK = asyncio.Lock()
_FETCH_CACHE_MAX_ENTRIES = 64
_SEARCH_QUERY_CONCURRENCY = 4
_FETCH_WAVE_SIZE = 4

# Last-resort public page only when search + heuristics fail. Never invent a D6 domain.
_FALLBACK_PUBLIC_URL = "https://example.com/"

_TAG = re.compile(r"<[^>]+>")
_STRIP_BLOCKS = re.compile(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")

_DOMAIN_QUERY = {
    "company": "company overview headquarters founded",
    "team": "founders leadership CEO executive team",
    "market": "market size industry TAM customers",
    "competition": "competitors alternatives vs",
    "product": "product platform features pricing",
    "traction": "funding customers growth ARR",
    "financials": "revenue funding series valuation",
    "capitalization": "funding investors valuation ownership",
    "legal": "lawsuit regulation compliance entity",
    "security": "security privacy SOC2 compliance breach",
    "governance": "board directors governance",
    "thesis_fit": "mission impact thesis",
}

# Extra deep-pass angles (GPT-Researcher-style bounded sub-queries).
_DOMAIN_DEEP_QUERY = {
    "company": [
        "legal name incorporation headquarters",
        "about company history founding year",
    ],
    "team": [
        "founder CEO LinkedIn biography",
        "executive team leadership names",
        "co-founder background prior company",
    ],
    "market": [
        "customers industry vertical segment",
        "addressable market demand report",
    ],
    "competition": [
        "competitors vs alternatives comparison",
        "competitive landscape peers",
    ],
    "product": [
        "product features pricing packaging",
        "platform documentation changelog",
    ],
    "traction": [
        "customer logos growth metrics users",
        "Series funding round announcement",
    ],
    "financials": [
        "revenue ARR funding valuation press",
        "Form D SEC filing investment",
    ],
    "capitalization": [
        "investors cap table ownership round",
        "venture funding lead investor",
    ],
    "legal": [
        "lawsuit settlement regulation enforcement",
        "registered entity Companies House SEC",
    ],
    "security": [
        "SOC2 ISO27001 security breach disclosure",
        "privacy trust center status page",
    ],
    "governance": [
        "board of directors advisors",
        "corporate governance policy",
    ],
    "thesis_fit": [
        "mission impact climate social",
        "company values purpose statement",
    ],
}

# Cap how many pages we keep from the company's own registrable domain.
_MAX_COMPANY_SITE = 1
_MAX_PER_DOMAIN = 1
# Deep research budgets (bounded — not unbounded crawl).
_DEFAULT_FETCH_NEED = 5
_DEEP_FETCH_NEED = 6
_CANDIDATE_LIMIT = 20


def _html_to_text(body: bytes) -> str:
    raw = body.decode("utf-8", errors="replace")
    raw = _STRIP_BLOCKS.sub(" ", raw)
    text = _TAG.sub(" ", raw)
    return re.sub(r"\s+", " ", text).strip()


def _company_slug(company_name: str) -> str:
    return _NON_ALNUM.sub("", company_name.lower().strip())


def heuristic_candidate_urls(company_name: str, domain_id: str) -> list[str]:
    """Sparse public URL guesses — domain-aware, never publisher search pages.

    Workstreams may share a *real article* when it is relevant, but must not all
    fall back to the same TechCrunch/Bloomberg/Reuters SERP chrome. News bodies
    come from SearXNG hits; heuristics only add homepage / reference / path hints.
    Never invent a D6 site.
    """
    slug = _company_slug(company_name)
    if not slug:
        return []
    wiki = f"https://en.wikipedia.org/wiki/{quote_plus(company_name.replace(' ', '_'))}"
    crunchbase = f"https://www.crunchbase.com/organization/{slug}"
    home = f"https://www.{slug}.com/"
    urls: list[str] = []

    # Domain-specific first so diversify keeps the right page per workstream.
    if domain_id == "company":
        urls.extend([home, f"https://www.{slug}.com/about", wiki, crunchbase])
    elif domain_id == "team":
        urls.extend(
            [
                f"https://www.linkedin.com/company/{slug}/",
                f"https://www.{slug}.com/about",
                f"https://www.{slug}.com/team",
                crunchbase,
            ]
        )
    elif domain_id == "product":
        urls.extend(
            [
                f"https://www.{slug}.com/product",
                f"https://www.{slug}.com/platform",
                f"https://www.{slug}.com/pricing",
                home,
            ]
        )
    elif domain_id in ("market", "competition"):
        urls.extend([home, wiki, crunchbase])
    elif domain_id in ("traction", "capitalization", "financials"):
        # Funding/traction should come from SearXNG articles — avoid SERP stubs.
        urls.extend([crunchbase, home])
    elif domain_id in ("security", "legal"):
        urls.extend(
            [
                f"https://www.{slug}.com/security",
                f"https://www.{slug}.com/trust",
                f"https://www.{slug}.com/privacy",
                home,
            ]
        )
    elif domain_id == "governance":
        urls.extend([f"https://www.{slug}.com/about", crunchbase, home])
    elif domain_id == "thesis_fit":
        urls.extend([f"https://www.{slug}.com/about", home, wiki])
    else:
        urls.extend([home, wiki, crunchbase])

    # Drop any accidental SERP-shaped URLs.
    return [u for u in urls if not url_looks_like_serp(u)]


def diversify_urls(
    urls: list[str],
    *,
    company_name: str,
    limit: int = 12,
    allow_serps: bool = False,
) -> list[str]:
    """Order candidates so distinct registrable domains come first.

    Prefers news *articles* over wiki/Crunchbase and over publisher SERPs.
    Keeps at most `_MAX_COMPANY_SITE` URLs from the company's own domain and
    `_MAX_PER_DOMAIN` from any other host. Same-site path variants are dropped.
    """
    company_dom = f"{_company_slug(company_name)}.com"
    cleaned = [(u or "").strip() for u in urls if (u or "").strip().startswith("http")]
    if not allow_serps:
        non_serp = [u for u in cleaned if not url_looks_like_serp(u)]
        # Keep SERPs only as last-resort overflow when nothing else exists.
        serps = [u for u in cleaned if url_looks_like_serp(u)]
        cleaned = non_serp or serps
    ranked = sorted(
        cleaned,
        key=lambda u: source_rank_score(u, company_dom=company_dom),
        reverse=True,
    )
    seen_url: set[str] = set()
    per_dom: dict[str, int] = {}
    primary: list[str] = []
    overflow: list[str] = []

    for u in ranked:
        key = u.rstrip("/").lower()
        if key in seen_url:
            continue
        seen_url.add(key)
        dom = registrable_domain(u) or "unknown"
        cap = _MAX_COMPANY_SITE if dom == company_dom else _MAX_PER_DOMAIN
        count = per_dom.get(dom, 0)
        if count >= cap:
            overflow.append(u)
            continue
        per_dom[dom] = count + 1
        primary.append(u)
        if len(primary) >= limit:
            break

    if len({registrable_domain(u) for u in primary if registrable_domain(u)}) < 3:
        for u in overflow:
            if len(primary) >= limit:
                break
            # Prefer filling with non-SERP overflow first.
            if url_looks_like_serp(u) and any(not url_looks_like_serp(x) for x in overflow):
                continue
            primary.append(u)
    return primary


async def searx_candidate_urls(
    *,
    firm_id: str,
    company_name: str,
    domain_id: str,
    max_results: int = 12,
    deep: bool = False,
    angles_only: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run several SearXNG queries in parallel and merge hits."""
    adapter = shared_searxng_adapter(settings.searxng_url, timeout_s=25.0)
    topic = _DOMAIN_QUERY.get(domain_id, "company")
    queries: list[tuple[str, str]] = []
    if not angles_only:
        queries.extend(
            [
                (f"{company_name} {topic}", "general"),
                (f'"{company_name}" {topic}', "general"),
                (
                    f"{company_name} (site:techcrunch.com OR site:reuters.com OR site:bloomberg.com "
                    f"OR site:forbes.com OR site:cnbc.com)",
                    "general",
                ),
                (f"{company_name} news {topic.split()[0]}", "news"),
                (f'"{company_name}" {topic.split()[0]}', "news"),
                (f"{company_name} site:wikipedia.org OR site:crunchbase.com", "general"),
            ]
        )
    if deep or angles_only:
        for angle in _DOMAIN_DEEP_QUERY.get(domain_id, [topic])[:3]:
            queries.append((f'"{company_name}" {angle}', "general"))
            queries.append((f"{company_name} {angle}", "news"))
    if not queries:
        queries.append((f"{company_name} {topic}", "general"))

    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    meta: dict[str, Any] = {
        "state": "unavailable",
        "result_count": 0,
        "engines_failed": [],
        "queries": [],
        "deep": deep,
        "angles_only": angles_only,
    }
    sem = asyncio.Semaphore(_SEARCH_QUERY_CONCURRENCY)

    async def _one(q: str, category: str) -> dict[str, Any]:
        async with sem:
            return await adapter.search(
                firm_id=firm_id,
                query=q,
                category=category,
                max_results=max_results,
            )

    payloads = await asyncio.gather(*[_one(q, cat) for q, cat in queries])
    for (q, category), payload in zip(queries, payloads, strict=True):
        meta["queries"].append(f"{category}:{q}")
        meta["state"] = payload.get("state") or meta["state"]
        if payload.get("state") == "ok":
            meta["state"] = "ok"
        meta["result_count"] = int(meta["result_count"]) + int(payload.get("result_count") or 0)
        failed = payload.get("engines_failed") or []
        meta["engines_failed"] = sorted(set(meta["engines_failed"]) | set(failed))
        for r in payload.get("results") or []:
            url = str(r.get("url") or "")
            key = url.rstrip("/").lower()
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(r)
    meta["unique_urls"] = len(merged)
    return merged, meta


async def discover_research_urls(
    *,
    firm_id: str,
    company_name: str,
    domain_id: str,
    deep: bool = False,
    exclude_urls: set[str] | None = None,
    website: str | None = None,
    angles_only: bool = False,
) -> dict[str, Any]:
    """SearXNG + sparse heuristics, diversified across registrable domains."""
    results, search_meta = await searx_candidate_urls(
        firm_id=firm_id,
        company_name=company_name,
        domain_id=domain_id,
        deep=deep,
        angles_only=angles_only,
    )
    site = (website or "").strip()
    site_urls: list[str] = []
    if site:
        if "://" not in site:
            site = f"https://{site}"
        base = site.rstrip("/")
        site_urls = [base + "/", base + "/about"]

    search_urls = [str(r.get("url") or "") for r in results]
    heur_urls = heuristic_candidate_urls(company_name, domain_id)
    # Website → search → heuristics; diversify preserves early preference.
    raw = site_urls + search_urls + heur_urls

    exclude = {u.rstrip("/").lower() for u in (exclude_urls or set())}
    if exclude:
        raw = [u for u in raw if u.rstrip("/").lower() not in exclude]

    urls = diversify_urls(raw, company_name=company_name, limit=_CANDIDATE_LIMIT)
    domains = sorted({registrable_domain(u) for u in urls if registrable_domain(u)})
    return {
        "urls": urls,
        "search_state": search_meta.get("state"),
        "search_result_count": search_meta.get("result_count", 0),
        "search_unique_urls": search_meta.get("unique_urls", 0),
        "search_queries": search_meta.get("queries") or [],
        "search_error": search_meta.get("error"),
        "engines_failed": search_meta.get("engines_failed") or [],
        "candidate_domains": domains,
        "candidate_domain_count": len(domains),
        "deep": deep,
    }


def _fetch_cache_key(firm_id: str, url: str) -> str:
    return f"{firm_id}|{canonicalize_url(url) or url.rstrip('/').lower()}"


async def _http_fetch_raw(url: str) -> dict[str, Any] | None:
    """Network-only fetch (no DB). Safe to run concurrently."""
    try:
        result = await execute_public_fetch(PublicFetchRequest(url=url))
        text = _html_to_text(result.body)
        passage = text[:500] if len(text) >= 80 else f"Retrieved public page {result.final_url}"
        return {
            "fetched": True,
            "url": result.final_url,
            "passage": passage,
            "text": text[:6000],
            "status_code": result.status_code,
            "body": result.body,
            "content_type": result.content_type or "text/html",
            "text_len": len(text),
        }
    except SandboxExecutionError:
        raise
    except SafeFetchError as exc:
        logger.info("public fetch blocked/failed: %s", exc.code)
    except Exception:  # noqa: BLE001
        # URLs, upstream error text, and validation errors may contain credentials.
        logger.warning("public fetch failed")
    return None


async def _persist_raw_evidence(
    session: AsyncSession,
    tenant: TenantContext,
    *,
    raw: dict[str, Any],
    requested_url: str,
) -> dict[str, Any]:
    snap, span = await persist_fetch_evidence(
        session,
        tenant,
        canonical_url=str(raw["url"]),
        body=raw["body"] if isinstance(raw.get("body"), (bytes, bytearray)) else str(raw.get("passage") or "").encode(),
        content_type=str(raw.get("content_type") or "text/html"),
        http_status=raw.get("status_code"),
        passage=str(raw.get("passage") or ""),
    )
    out = {
        "ok": True,
        "fetched": True,
        "url": raw["url"],
        "snapshot_id": snap.snapshot_id,
        "span_id": span.span_id,
        "passage": raw.get("passage"),
        "text": raw.get("text"),
        "status_code": raw.get("status_code"),
        "body": raw.get("body"),
        "content_type": raw.get("content_type") or "text/html",
        "text_len": raw.get("text_len") or 0,
    }
    cache_key = _fetch_cache_key(tenant.firm_id, requested_url)
    final_key = _fetch_cache_key(tenant.firm_id, str(raw["url"]))
    async with _FETCH_CACHE_LOCK:
        # Cache network bytes only. DB identifiers from this transaction may be
        # rolled back, or not yet visible to another domain's transaction.
        _FETCH_CACHE[cache_key] = dict(raw)
        _FETCH_CACHE[final_key] = dict(raw)
        while len(_FETCH_CACHE) > _FETCH_CACHE_MAX_ENTRIES:
            _FETCH_CACHE.pop(next(iter(_FETCH_CACHE)))
    return out


async def fetch_public_evidence(
    session: AsyncSession,
    tenant: TenantContext,
    *,
    url: str = _FALLBACK_PUBLIC_URL,
) -> dict[str, Any]:
    """SafeFetch a public URL and persist snapshot/span. Falls back to offline stub."""
    cache_key = _fetch_cache_key(tenant.firm_id, url)
    async with _FETCH_CACHE_LOCK:
        hit = _FETCH_CACHE.get(cache_key)
    if hit is not None:
        return await _persist_raw_evidence(session, tenant, raw=dict(hit), requested_url=url)

    raw = await _http_fetch_raw(url)
    if raw is not None:
        return await _persist_raw_evidence(session, tenant, raw=raw, requested_url=url)

    stub = f"Offline public stub for {url} (no live fetch)."
    snap, span = await persist_fetch_evidence(
        session,
        tenant,
        canonical_url=url,
        body=stub.encode("utf-8"),
        content_type="text/plain",
        http_status=None,
        passage=stub,
    )
    return {
        "ok": True,
        "fetched": False,
        "url": url,
        "snapshot_id": snap.snapshot_id,
        "span_id": span.span_id,
        "passage": stub,
        "text": stub,
        "status_code": None,
        "body": stub.encode("utf-8"),
        "content_type": "text/plain",
        "text_len": len(stub),
    }


async def fetch_best_evidence(
    session: AsyncSession,
    tenant: TenantContext,
    *,
    urls: list[str],
    need: int = _DEFAULT_FETCH_NEED,
    company_name: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch until we have `need` pages from distinct registrable domains.

    Prefers article/body pages over publisher SERPs and wiki/Crunchbase.
    Same-site path variants are skipped once that registrable domain is covered.
    Fetches run in small parallel waves; DB persist stays sequential per URL.
    """
    company_dom = f"{_company_slug(company_name)}.com" if company_name else ""
    ordered = diversify_urls(urls, company_name=company_name or "", limit=max(len(urls), need + 6))
    article_urls = [u for u in ordered if not url_looks_like_serp(u)]
    serp_urls = [u for u in ordered if url_looks_like_serp(u)]
    fetched: list[dict[str, Any]] = []
    covered: set[str] = set()

    def _enough() -> bool:
        rich = {
            registrable_domain(e["url"])
            for e in fetched
            if e.get("text_len", 0) >= 80 and registrable_domain(e["url"])
        }
        preferred = {
            registrable_domain(e["url"])
            for e in fetched
            if source_rank_score(str(e.get("url") or ""), company_dom=company_dom) >= 20
            and registrable_domain(e["url"])
        }
        return len(rich) >= need and len(preferred) >= min(3, need)

    async def _accept(ev: dict[str, Any], *, accept_serp: bool) -> bool:
        nonlocal fetched, covered
        if not ev.get("fetched"):
            return False
        body_text = str(ev.get("text") or ev.get("passage") or "")
        final_url = str(ev.get("url") or "")
        if url_looks_like_serp(final_url) and not accept_serp:
            return False
        if not accept_serp and not passage_usable_for_domain(body_text):
            if int(ev.get("text_len") or 0) < 200:
                return False
        final_dom = registrable_domain(final_url)
        if final_dom and final_dom in covered:
            return False
        fetched.append(ev)
        if final_dom:
            covered.add(final_dom)
        return True

    async def _wave(candidates: list[str], *, accept_serp: bool) -> None:
        nonlocal fetched, covered
        pending = [
            u
            for u in candidates
            if not ((dom := registrable_domain(u)) and dom in covered)
            and (accept_serp or not url_looks_like_serp(u))
        ]
        i = 0
        while i < len(pending) and not _enough() and len(covered) < need + 2:
            batch = [
                u
                for u in pending[i : i + _FETCH_WAVE_SIZE]
                if not ((d := registrable_domain(u)) and d in covered)
            ]
            i += _FETCH_WAVE_SIZE
            if not batch:
                continue
            # HTTP in parallel; cache hits skip network; DB persist stays serial.
            prepared: list[tuple[str, dict[str, Any] | None]] = []
            for u in batch:
                cache_key = _fetch_cache_key(tenant.firm_id, u)
                async with _FETCH_CACHE_LOCK:
                    hit = _FETCH_CACHE.get(cache_key)
                if hit is not None:
                    prepared.append((u, dict(hit)))
                else:
                    prepared.append((u, None))
            to_fetch = [u for u, ev in prepared if ev is None]
            raws = await asyncio.gather(*[_http_fetch_raw(u) for u in to_fetch]) if to_fetch else []
            raw_by_url = dict(zip(to_fetch, raws, strict=True))
            for u, cached in prepared:
                raw = cached if cached is not None else raw_by_url.get(u)
                if raw is None:
                    continue
                ev = await _persist_raw_evidence(session, tenant, raw=raw, requested_url=u)
                await _accept(ev, accept_serp=accept_serp)
                if _enough() or len(covered) >= need + 2:
                    return

    await _wave(article_urls[:24], accept_serp=False)
    if len(fetched) < min(2, need):
        await _wave(serp_urls[:8], accept_serp=True)

    def _rank(e: dict[str, Any]) -> tuple[int, int, int]:
        u = str(e.get("url") or "")
        usable = 1 if passage_usable_for_domain(str(e.get("text") or e.get("passage") or "")) else 0
        return (usable, source_rank_score(u, company_dom=company_dom), int(e.get("text_len") or 0))

    fetched.sort(key=_rank, reverse=True)
    if not fetched:
        fetched.append(await fetch_public_evidence(session, tenant, url=_FALLBACK_PUBLIC_URL))
    return fetched[: max(need, 1)]


def _evidence_needs_deepen(
    evidence_list: list[dict[str, Any]],
    *,
    company_name: str,
    domain_id: str,
) -> bool:
    """True when first pass is too thin for the domain (docs: bounded follow-up)."""
    urls = [str(e.get("url") or "") for e in evidence_list if e.get("fetched")]
    if not urls:
        return True
    if not has_preferred_independent_source(urls):
        # Company site alone is OK for company/product, still deepen for team/market/etc.
        company_dom = f"{_company_slug(company_name)}.com"
        domains = {registrable_domain(u) for u in urls if registrable_domain(u)}
        if domain_id in ("company", "product", "thesis_fit") and company_dom in domains:
            # Deepen unless we also have a non-reference third party.
            non_ref = domains - REFERENCE_ONLY_DOMAINS - {company_dom}
            return not non_ref
        return True
    if domain_id == "team":
        # Team almost always needs a second angled pass for named people.
        return True
    return False


def claim_from_evidence(
    *,
    firm_id: str,
    assessment_id: UUID,
    revision: int,
    domain_id: DomainId,
    statement: str,
    subject: str,
    snapshot_id: str,
    span_id: str,
    source_url: str,
    source_urls: list[str] | None = None,
    extra_snapshot_ids: list[str] | None = None,
    extra_span_ids: list[str] | None = None,
    confidence: Decimal = Decimal("0.60"),
    verification_status: str = "extracted",
    trust_state: str = "supported",
    passage: str | None = None,
    apply_grounding: bool = True,
) -> Claim:
    numeric_facts: list[str] = []
    numeric_grounded: list[str] = []
    claim_type = "fact"
    if apply_grounding and trust_state == "supported":
        grounding = ground_numeric_statement(statement, passage or "")
        numeric_facts = list(grounding.facts)
        numeric_grounded = list(grounding.supported_facts)
        if grounding.facts:
            trust_state, verification_status, claim_type = trust_for_grounding(grounding)
            if not grounding.ok_for_supported:
                # Cap confidence — ungrounded metrics must not look diligence-grade.
                confidence = min(confidence, Decimal("0.35"))
                if grounding.detail and grounding.detail not in statement:
                    statement = f"{statement.rstrip()} [{grounding.detail}]"[:500]
    snap_ids = [UUID(snapshot_id)]
    for sid in extra_snapshot_ids or []:
        u = UUID(sid)
        if u not in snap_ids:
            snap_ids.append(u)
    span_ids = [UUID(span_id)]
    for sid in extra_span_ids or []:
        u = UUID(sid)
        if u not in span_ids:
            span_ids.append(u)
    return Claim(
        claim_id=uuid4(),
        firm_id=firm_id,
        assessment_id=assessment_id,
        revision=revision,
        domain_id=domain_id,
        statement=statement,
        claim_type=claim_type,  # type: ignore[arg-type]
        subject=subject,
        trust_state=trust_state,  # type: ignore[arg-type]
        verification_status=verification_status,  # type: ignore[arg-type]
        confidence=confidence,
        evidence_quality="mixed" if not numeric_facts else ("good" if numeric_grounded == numeric_facts else "weak"),
        evidence_span_ids=span_ids,
        snapshot_ids=snap_ids,
        source_urls=list(source_urls) if source_urls else [source_url],
        numeric_facts=numeric_facts,
        numeric_facts_grounded=numeric_grounded,
        company_authored=False,
        extracted_at=datetime.now(timezone.utc),
    )


def corroborate_public_docs(
    *,
    claim_key: str,
    documents: list[SourceDocument],
    query_terms: list[str],
) -> dict[str, Any]:
    result = rank_and_corroborate(
        claim_key=claim_key,
        documents=documents,
        query_terms=query_terms,
    )
    return {
        "independent_count": result.independent_count,
        "independent_domains": result.independent_domains,
        "syndicated_groups": result.syndicated_groups,
        "ranked": [
            {
                "canonical_url": r.canonical_url,
                "relevance": str(r.relevance),
                "independence_group": r.independence_group,
                "evidence_quality": r.evidence_quality,
            }
            for r in result.ranked
        ],
    }


def _ground_statement(statement: str, passage: str, company_name: str) -> str:
    """Keep LLM claim, but append a short evidence cue when passage is real."""
    base = (statement or "").strip()
    if not base:
        base = f"{company_name}: public signal recorded."
    # Do not glue wiki chrome onto an honest "not evidenced" admission.
    if statement_admits_evidence_gap(base):
        return base[:500]
    cue = (passage or "").strip()
    if (
        len(cue) < 40
        or cue.startswith("Offline public stub")
        or cue.startswith("Retrieved public page")
        or passage_is_chrome(cue)
    ):
        return base[:500]
    snippet = cue[:160].rstrip()
    if snippet.lower() in base.lower():
        return base[:500]
    return f"{base} Evidence: “{snippet}…”"[:500]


async def research_domain_claims(
    session: AsyncSession,
    tenant: TenantContext,
    *,
    assessment_id: str,
    revision: int,
    domain_id: str,
    company_name: str,
    statement: str | None = None,
    draft_statement: Any | None = None,
    allow_deep_followup: bool = True,
    website: str | None = None,
) -> dict[str, Any]:
    """SearXNG/heuristic discover → SafeFetch → optional deep follow-up → claim.

    Prefer ``draft_statement(passages, source_urls) -> (statement, used_llm)`` so claims
    are domain-specific and grounded in fetched pages. ``statement`` remains for tests.
    """
    from collections.abc import Awaitable, Callable

    discovery = await discover_research_urls(
        firm_id=tenant.firm_id,
        company_name=company_name,
        domain_id=domain_id,
        website=website,
    )
    evidence_list = await fetch_best_evidence(
        session,
        tenant,
        urls=discovery["urls"],
        need=_DEFAULT_FETCH_NEED,
        company_name=company_name,
    )
    deep_used = False
    if allow_deep_followup and _evidence_needs_deepen(
        evidence_list, company_name=company_name, domain_id=domain_id
    ):
        deep_used = True
        already = {str(e.get("url") or "").rstrip("/").lower() for e in evidence_list}
        deep_discovery = await discover_research_urls(
            firm_id=tenant.firm_id,
            company_name=company_name,
            domain_id=domain_id,
            deep=True,
            angles_only=True,
            exclude_urls=already,
            website=website,
        )
        # Merge query metadata for UI/debug.
        discovery = {
            **discovery,
            "deep_pass": True,
            "deep_search_queries": deep_discovery.get("search_queries") or [],
            "deep_candidate_domains": deep_discovery.get("candidate_domains") or [],
            "search_queries": list(discovery.get("search_queries") or [])
            + list(deep_discovery.get("search_queries") or []),
            "candidate_domains": sorted(
                set(discovery.get("candidate_domains") or [])
                | set(deep_discovery.get("candidate_domains") or [])
            ),
            "engines_failed": sorted(
                set(discovery.get("engines_failed") or [])
                | set(deep_discovery.get("engines_failed") or [])
            ),
        }
        more = await fetch_best_evidence(
            session,
            tenant,
            urls=deep_discovery["urls"],
            need=_DEEP_FETCH_NEED,
            company_name=company_name,
        )
        seen_dom = {
            registrable_domain(str(e.get("url") or ""))
            for e in evidence_list
            if registrable_domain(str(e.get("url") or ""))
        }
        for e in more:
            d = registrable_domain(str(e.get("url") or ""))
            if d and d in seen_dom:
                continue
            evidence_list.append(e)
            if d:
                seen_dom.add(d)
        # Re-rank merged set.
        company_dom = f"{_company_slug(company_name)}.com"
        evidence_list.sort(
            key=lambda e: (
                source_rank_score(str(e.get("url") or ""), company_dom=company_dom),
                int(e.get("text_len") or 0),
            ),
            reverse=True,
        )
        evidence_list = evidence_list[: max(_DEEP_FETCH_NEED, _DEFAULT_FETCH_NEED)]

    def _evidence_usable(e: dict[str, Any]) -> bool:
        u = str(e.get("url") or "")
        if url_looks_like_serp(u):
            return False
        return passage_usable_for_domain(str(e.get("text") or e.get("passage") or ""))

    usable_evidence = [e for e in evidence_list if _evidence_usable(e)]
    ranked_evidence = usable_evidence or evidence_list
    primary = ranked_evidence[0]
    extras = [e for e in ranked_evidence[1:] if e is not primary]

    # Cite distinct non-SERP pages first — workstreams should not all list the
    # same publisher search URLs as "evidence" when article bodies exist.
    source_urls: list[str] = []
    for e in ranked_evidence:
        u = str(e.get("url") or "")
        if (
            u
            and "example.com" not in u
            and not url_looks_like_serp(u)
            and u not in source_urls
            and registrable_domain(u)
            not in {registrable_domain(x) for x in source_urls}
        ):
            source_urls.append(u)
    if not source_urls:
        source_urls = [str(primary.get("url") or "")]

    passages = [
        str(e.get("text") or e.get("passage") or "")
        for e in ranked_evidence
        if passage_usable_for_domain(str(e.get("text") or e.get("passage") or ""))
    ]
    if not passages:
        passages = [
            str(e.get("text") or e.get("passage") or "")
            for e in evidence_list
            if e.get("text") or e.get("passage")
        ]
    used_llm = False
    if draft_statement is not None:
        draft_fn: Callable[[list[str], list[str]], Awaitable[tuple[str, bool]]] = draft_statement
        statement, used_llm = await draft_fn(passages, source_urls[:6])
        # If the model admits a gap after deep pass, keep that honesty.
        if (
            allow_deep_followup
            and not deep_used
            and statement_admits_evidence_gap(statement or "")
        ):
            # One more angled pass when the draft itself says evidence is missing.
            deep_used = True
            already = {str(e.get("url") or "").rstrip("/").lower() for e in evidence_list}
            deep_discovery = await discover_research_urls(
                firm_id=tenant.firm_id,
                company_name=company_name,
                domain_id=domain_id,
                deep=True,
                angles_only=True,
                exclude_urls=already,
                website=website,
            )
            more = await fetch_best_evidence(
                session,
                tenant,
                urls=deep_discovery["urls"],
                need=_DEEP_FETCH_NEED,
                company_name=company_name,
            )
            seen_dom = {
                registrable_domain(str(e.get("url") or ""))
                for e in evidence_list
                if registrable_domain(str(e.get("url") or ""))
            }
            for e in more:
                d = registrable_domain(str(e.get("url") or ""))
                if d and d in seen_dom:
                    continue
                evidence_list.append(e)
                if d:
                    seen_dom.add(d)
            usable_evidence = [e for e in evidence_list if _evidence_usable(e)]
            ranked_evidence = usable_evidence or evidence_list
            primary = ranked_evidence[0]
            extras = ranked_evidence[1:]
            source_urls = []
            for e in ranked_evidence:
                u = str(e.get("url") or "")
                if (
                    u
                    and "example.com" not in u
                    and not url_looks_like_serp(u)
                    and u not in source_urls
                ):
                    source_urls.append(u)
            if not source_urls:
                source_urls = [str(primary.get("url") or "")]
            passages = [
                str(e.get("text") or e.get("passage") or "")
                for e in ranked_evidence
                if passage_usable_for_domain(str(e.get("text") or e.get("passage") or ""))
            ] or [
                str(e.get("text") or e.get("passage") or "")
                for e in evidence_list
                if e.get("text") or e.get("passage")
            ]
            statement, used_llm = await draft_fn(passages, source_urls[:6])
            discovery = {
                **discovery,
                "deep_pass": True,
                "deep_after_gap": True,
                "search_queries": list(discovery.get("search_queries") or [])
                + list(deep_discovery.get("search_queries") or []),
            }
    elif not statement:
        statement = f"{company_name}: public signal recorded for {domain_id}"

    docs = [
        SourceDocument(
            url=primary["url"],
            title="Primary public source",
            snippet=(primary.get("passage") or "")[:240],
            content_text=primary.get("text") or primary.get("passage") or "",
            search_rank=1,
            is_primary=True,
        )
    ]
    for idx, extra in enumerate(extras[:5], start=2):
        docs.append(
            SourceDocument(
                url=extra["url"],
                title=f"Public source {idx}",
                snippet=(extra.get("passage") or "")[:240],
                content_text=extra.get("text") or extra.get("passage") or "",
                search_rank=idx,
                is_primary=False,
            )
        )
    if len(docs) < 2:
        # Syndicated mirror of primary — must not inflate independence.
        docs.append(
            SourceDocument(
                url=primary["url"].rstrip("/") + "/mirror",
                title="Syndicated copy",
                snippet=(primary.get("passage") or "")[:240],
                content_text=primary.get("text") or primary.get("passage") or "",
                search_rank=2,
                is_primary=False,
            )
        )

    corr = corroborate_public_docs(
        claim_key=f"{company_name}:{domain_id}",
        documents=docs,
        query_terms=[company_name, domain_id, "company"],
    )

    grounded = _ground_statement(statement or "", primary.get("passage") or "", company_name)
    real_fetch = bool(primary.get("fetched")) and "example.com" not in primary["url"]
    gap = statement_admits_evidence_gap(grounded)
    # Attach every usable independent page — sufficiency counts domains, not claim rows.
    extra_snaps: list[str] = []
    extra_spans: list[str] = []
    for e in ranked_evidence[1:]:
        sid = str(e.get("snapshot_id") or "")
        spid = str(e.get("span_id") or "")
        if sid and sid != str(primary.get("snapshot_id")) and sid not in extra_snaps:
            extra_snaps.append(sid)
        if spid and spid != str(primary.get("span_id")) and spid not in extra_spans:
            extra_spans.append(spid)
    claim = claim_from_evidence(
        firm_id=tenant.firm_id,
        assessment_id=UUID(assessment_id),
        revision=revision,
        domain_id=domain_id,  # type: ignore[arg-type]
        statement=grounded,
        subject=domain_id,
        snapshot_id=primary["snapshot_id"],
        span_id=primary["span_id"],
        source_url=primary["url"],
        source_urls=source_urls[:6],
        extra_snapshot_ids=extra_snaps,
        extra_span_ids=extra_spans,
        confidence=(
            Decimal("0.30")
            if gap
            else (Decimal("0.72") if real_fetch else Decimal("0.45"))
        ),
        verification_status="insufficient" if gap else "extracted",
        trust_state="insufficient" if gap else "supported",
        passage=primary.get("text") or primary.get("passage") or "",
        apply_grounding=not gap,
    )
    stored = await insert_claim(session, tenant, claim)
    claims: list[Claim] = [stored]
    contradictions: list[ContradictionRecord] = []
    contradiction_id = None

    # Only emit the canned identity caution when evidence is thin (wiki/CB-only or none).
    # Strong company-site / news evidence should not be poisoned by boilerplate contradictions.
    if domain_id == "company" and identity_evidence_is_thin(
        source_urls=source_urls[:6], company_name=company_name
    ):
        alt_source = extras[0] if extras else None
        if alt_source is None:
            synd_span = await insert_span(
                session,
                tenant,
                snapshot_id=primary["snapshot_id"],
                text=(primary.get("passage") or "")[:400] or "syndicated copy",
                start_offset=0,
            )
            alt_span_id = synd_span.span_id
            alt_url = primary["url"].rstrip("/") + "/mirror"
            alt_snap = primary["snapshot_id"]
        else:
            alt_span_id = alt_source["span_id"]
            alt_url = alt_source["url"]
            alt_snap = alt_source["snapshot_id"]

        alt_statement = (
            f"{company_name}: public identity signals are incomplete; "
            "registry confirmation still required."
        )
        alt = claim_from_evidence(
            firm_id=tenant.firm_id,
            assessment_id=UUID(assessment_id),
            revision=revision,
            domain_id=domain_id,  # type: ignore[arg-type]
            statement=alt_statement,
            subject=domain_id,
            snapshot_id=alt_snap,
            span_id=alt_span_id,
            source_url=alt_url,
            confidence=Decimal("0.40"),
            verification_status="contested",
            trust_state="contested",
            apply_grounding=False,
        )
        alt_stored = await insert_claim(session, tenant, alt)
        claims.append(alt_stored)
        record = ContradictionRecord(
            contradiction_id=uuid4(),
            firm_id=tenant.firm_id,
            assessment_id=UUID(assessment_id),
            revision=revision,
            domain_ids=["company"],
            claim_ids=[stored.claim_id, alt_stored.claim_id],
            contradiction_type="other",
            severity="medium",
            explanation=(
                "Primary screening claim and cautionary identity claim conflict on "
                "completeness of public company identity evidence (thin reference-only sources)."
            ),
            evidence_for=[UUID(primary["span_id"])],
            evidence_against=[UUID(alt_span_id)],
            resolution="open",
            human_review_state="pending",
            trust_impact="contested",
            version=1,
        )
        saved = await insert_contradiction(session, tenant, record)
        contradiction_id = str(saved.contradiction_id)
        contradictions = [saved]

    return {
        "claim": stored,
        "claims": claims,
        "statement": grounded,
        "used_llm": used_llm,
        "fetched": real_fetch,
        "corroboration": corr,
        "contradiction_id": contradiction_id,
        "contradictions": contradictions,
        "snapshot_id": primary["snapshot_id"],
        "span_id": primary["span_id"],
        "source_url": primary["url"],
        "source_urls": source_urls[:6],
        "deep_pass": deep_used,
        "discovery": {
            "search_state": discovery.get("search_state"),
            "search_result_count": discovery.get("search_result_count"),
            "search_unique_urls": discovery.get("search_unique_urls"),
            "search_queries": (discovery.get("search_queries") or [])[:16],
            "candidate_urls": discovery.get("urls", [])[:12],
            "candidate_domains": discovery.get("candidate_domains"),
            "candidate_domain_count": len(discovery.get("candidate_domains") or []),
            "fetched_urls": [e["url"] for e in evidence_list],
            "fetched_domains": sorted(
                {registrable_domain(e["url"]) for e in evidence_list if registrable_domain(e["url"])}
            ),
            "engines_failed": discovery.get("engines_failed"),
            "deep_pass": deep_used,
            "deep_after_gap": bool(discovery.get("deep_after_gap")),
        },
    }
