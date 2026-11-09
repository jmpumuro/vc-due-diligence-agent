# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Thesis contributors
"""Public-source breadth checks — wiki/Crunchbase alone are not sufficient."""

from __future__ import annotations

import re

from thesis_api.services.search.normalize import registrable_domain

REFERENCE_ONLY_DOMAINS = frozenset(
    {
        "wikipedia.org",
        "crunchbase.com",
        "wikidata.org",
    }
)

# Prefer these over wiki/Crunchbase when ranking candidates (news/primary).
PREFERRED_INDEPENDENT_DOMAINS = frozenset(
    {
        "techcrunch.com",
        "reuters.com",
        "bloomberg.com",
        "wsj.com",
        "ft.com",
        "forbes.com",
        "theinformation.com",
        "nytimes.com",
        "sec.gov",
        "github.com",
        "linkedin.com",
        "businesswire.com",
        "prnewswire.com",
        "cnbc.com",
        "theverge.com",
        "wired.com",
        "mobihealthnews.com",
        "streetinsider.com",
        "law360.com",
    }
)

# Search/index URLs are not diligence evidence — they recycle the same chrome
# across every workstream and rarely contain domain-specific facts.
_SERP_PATH_MARKERS = (
    "/search?",
    "/search/",
    "/site-search",
    "/?s=",
    "&s=",
    "query=",
    "/topics/",
)

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def url_looks_like_serp(url: str) -> bool:
    """True for publisher search/index pages (not article bodies)."""
    u = (url or "").lower()
    if not u.startswith("http"):
        return False
    if any(m in u for m in _SERP_PATH_MARKERS):
        return True
    # Bare section hubs without an article slug (e.g. /business/).
    path = u.split("?", 1)[0].rstrip("/")
    parts = [p for p in path.split("/")[3:] if p]
    if len(parts) <= 1 and any(
        h in u
        for h in (
            "techcrunch.com",
            "reuters.com",
            "bloomberg.com",
            "forbes.com",
            "cnbc.com",
        )
    ):
        return True
    return False


def source_domains_from_urls(urls: list[str]) -> set[str]:
    out: set[str] = set()
    for u in urls:
        d = registrable_domain(u or "")
        if d and "example.com" not in d:
            out.add(d)
    return out


def has_non_reference_source(urls: list[str]) -> bool:
    """True when at least one URL is outside wiki/Crunchbase/Wikidata."""
    return bool(source_domains_from_urls(urls) - REFERENCE_ONLY_DOMAINS)


def has_preferred_independent_source(urls: list[str]) -> bool:
    """True when at least one preferred news/primary domain is present."""
    return bool(source_domains_from_urls(urls) & PREFERRED_INDEPENDENT_DOMAINS)


def source_rank_score(url: str, *, company_dom: str = "") -> int:
    """Higher is better when ordering fetch candidates."""
    d = registrable_domain(url or "")
    if not d or "example.com" in d:
        return -10
    # SERPs must lose to real articles on the same host.
    if url_looks_like_serp(url):
        return -5
    if d in PREFERRED_INDEPENDENT_DOMAINS:
        return 50
    if company_dom and d == company_dom:
        return 30
    if d in REFERENCE_ONLY_DOMAINS:
        return 5
    return 20


def identity_evidence_is_thin(*, source_urls: list[str], company_name: str) -> bool:
    """True when company identity rests only on reference indexes (or nothing real)."""
    domains = source_domains_from_urls(source_urls)
    if not domains:
        return True
    slug = _NON_ALNUM.sub("", company_name.lower().strip())
    company_dom = f"{slug}.com" if slug else ""
    if company_dom and company_dom in domains:
        return False
    if has_non_reference_source(source_urls):
        return False
    return domains <= REFERENCE_ONLY_DOMAINS


_NO_EVIDENCE_MARKERS = (
    "not evidenced",
    "not yet evidenced",
    "do not provide specific",
    "does not provide specific",
    "cited sources do not",
    "cited passages do not",
    "cited pages do not",
    "no names appear",
    "are not evidenced",
    "is not evidenced",
    "no specific customer",
    "no specific information",
    "do not contain relevant",
    "does not contain relevant",
    "information is not evidenc",
    "not evidenc",
)


def statement_admits_evidence_gap(statement: str) -> bool:
    """True when the drafted claim itself says the domain is not evidenced on the pages."""
    s = (statement or "").lower()
    return any(m in s for m in _NO_EVIDENCE_MARKERS)


def passage_is_chrome(passage: str) -> bool:
    """Skip wiki/nav/SERP chrome that is not diligence evidence."""
    p = (passage or "").lower()
    if len(p) < 40:
        return True
    chrome = (
        "jump to content",
        "main menu",
        "move to sidebar",
        "toggle the table of contents",
        "search results",
        "skip to content",
        "skip to main content",
        "results for",
        "did you mean",
    )
    hits = sum(1 for c in chrome if c in p)
    return hits >= 2


def passage_usable_for_domain(passage: str) -> bool:
    """False for empty/stub/chrome passages that should not ground claims."""
    p = (passage or "").strip()
    if len(p) < 60:
        return False
    if p.startswith("Offline public stub") or p.startswith("Retrieved public page"):
        return False
    return not passage_is_chrome(p)
