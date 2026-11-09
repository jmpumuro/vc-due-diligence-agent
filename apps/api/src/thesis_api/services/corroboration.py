"""Source relevance vs independent corroboration — separate concepts.

A high search rank is not automatic credibility. Syndicated copies of one
announcement do not count as independent confirmation. Contradictory sources
are preserved even at lower relevance.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from urllib.parse import urlparse

from thesis_api.services.search.normalize import canonicalize_url, registrable_domain


@dataclass
class SourceDocument:
    url: str
    title: str = ""
    snippet: str = ""
    content_text: str = ""
    published_at: datetime | None = None
    search_rank: int | None = None
    is_primary: bool = False
    company_authored: bool = False


@dataclass
class RankedSource:
    canonical_url: str
    domain: str
    relevance: Decimal
    independence_group: str
    is_primary: bool
    freshness_days: int | None
    evidence_quality: str
    company_authored: bool
    search_rank: int | None
    near_duplicate_of: str | None = None
    preserve_despite_low_relevance: bool = False


@dataclass
class CorroborationResult:
    claim_key: str
    ranked: list[RankedSource]
    independent_domains: list[str]
    independent_count: int
    syndicated_groups: dict[str, list[str]] = field(default_factory=dict)
    contradictory_urls: list[str] = field(default_factory=list)


_WS = re.compile(r"\s+")


def content_fingerprint(text: str) -> str:
    norm = _WS.sub(" ", (text or "").strip().lower())
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def near_duplicate(a: str, b: str, *, threshold: float = 0.92) -> bool:
    """Cheap Jaccard-on-shingles near-dup detector for syndicated copy."""
    def shingles(t: str) -> set[str]:
        toks = _WS.sub(" ", t.lower()).split()
        if len(toks) < 5:
            return {" ".join(toks)}
        return {" ".join(toks[i : i + 3]) for i in range(len(toks) - 2)}

    sa, sb = shingles(a), shingles(b)
    if not sa or not sb:
        return False
    inter = len(sa & sb)
    union = len(sa | sb)
    return (inter / union) >= threshold if union else False


def relevance_score(doc: SourceDocument, *, query_terms: list[str]) -> Decimal:
    """Search relevance only — not credibility or independence."""
    blob = f"{doc.title} {doc.snippet} {doc.content_text[:2000]}".lower()
    hits = sum(1 for t in query_terms if t.lower() in blob)
    base = Decimal(hits) / Decimal(max(len(query_terms), 1))
    if doc.search_rank is not None and doc.search_rank > 0:
        # mild rank boost; never alone enough for "credible"
        base += Decimal("0.05") * Decimal(max(0, 11 - min(doc.search_rank, 10)))
    if doc.is_primary:
        base += Decimal("0.1")
    return min(base, Decimal("1"))


def independence_group_id(doc: SourceDocument) -> str:
    """Group syndicated / mirrored content so copies share one independence slot."""
    domain = registrable_domain(doc.url)
    fp = content_fingerprint(doc.content_text or doc.snippet or doc.title)
    return f"{domain}:{fp[:16]}"


def evidence_quality_label(doc: SourceDocument) -> str:
    if doc.company_authored:
        return "weak"
    if doc.is_primary:
        return "strong"
    domain = registrable_domain(doc.url)
    # Heuristic: filings / regs domains stronger than blogs
    if any(x in domain for x in ("sec.gov", "gov", "edgar", "companieshouse")):
        return "strong"
    if doc.content_text and len(doc.content_text) > 500:
        return "good"
    return "mixed"


def rank_and_corroborate(
    *,
    claim_key: str,
    documents: list[SourceDocument],
    query_terms: list[str],
    contradictory_urls: list[str] | None = None,
    now: datetime | None = None,
) -> CorroborationResult:
    now = now or datetime.now(timezone.utc)
    contradictory = set(contradictory_urls or [])
    ranked: list[RankedSource] = []
    seen_canon: dict[str, str] = {}
    groups: dict[str, list[str]] = {}
    fingerprints: list[tuple[str, str]] = []  # canon, text

    for doc in documents:
        canon = canonicalize_url(doc.url)
        if not canon:
            continue
        if canon in seen_canon:
            continue
        # near-dup against prior
        near_of = None
        text = doc.content_text or doc.snippet or doc.title
        for prev_canon, prev_text in fingerprints:
            if near_duplicate(text, prev_text):
                near_of = prev_canon
                break
        seen_canon[canon] = canon
        fingerprints.append((canon, text))
        gid = independence_group_id(doc) if near_of is None else f"synd:{near_of}"
        groups.setdefault(gid, []).append(canon)
        fresh = None
        if doc.published_at:
            fresh = max(0, (now - doc.published_at).days)
        rel = relevance_score(doc, query_terms=query_terms)
        preserve = canon in contradictory
        ranked.append(
            RankedSource(
                canonical_url=canon,
                domain=registrable_domain(canon),
                relevance=rel,
                independence_group=gid,
                is_primary=doc.is_primary,
                freshness_days=fresh,
                evidence_quality=evidence_quality_label(doc),
                company_authored=doc.company_authored,
                search_rank=doc.search_rank,
                near_duplicate_of=near_of,
                preserve_despite_low_relevance=preserve,
            )
        )

    ranked.sort(key=lambda r: (r.preserve_despite_low_relevance, r.relevance), reverse=True)

    # Independent = unique independence groups that are not near-dups of another
    independent_domains: list[str] = []
    seen_groups: set[str] = set()
    for r in ranked:
        if r.near_duplicate_of:
            continue
        if r.independence_group in seen_groups:
            continue
        if r.company_authored:
            continue
        seen_groups.add(r.independence_group)
        if r.domain not in independent_domains:
            independent_domains.append(r.domain)

    return CorroborationResult(
        claim_key=claim_key,
        ranked=ranked,
        independent_domains=independent_domains,
        independent_count=len(seen_groups),
        syndicated_groups={k: v for k, v in groups.items() if len(v) > 1},
        contradictory_urls=sorted(contradictory),
    )

