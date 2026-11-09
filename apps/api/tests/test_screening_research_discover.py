"""Real-research discovery helpers (no live network required)."""

from __future__ import annotations

from thesis_api.services.screening_research import (
    _company_slug,
    diversify_urls,
    heuristic_candidate_urls,
)
from thesis_api.services.source_quality import source_rank_score, url_looks_like_serp


def test_company_slug() -> None:
    assert _company_slug("SonderMind") == "sondermind"
    assert _company_slug("OpenAI Smoke Co") == "openaismokeco"


def test_heuristic_urls_sparse_not_path_flood() -> None:
    urls = heuristic_candidate_urls("SonderMind", "company")
    assert any(u.rstrip("/").endswith("sondermind.com") or "sondermind.com/" in u for u in urls)
    company_paths = [u for u in urls if "sondermind.com" in u]
    assert len(company_paths) <= 2
    assert any("wikipedia.org" in u or "crunchbase.com" in u for u in urls)
    # Must never inject publisher SERPs as shared "evidence" for every domain.
    assert not any(url_looks_like_serp(u) for u in urls)


def test_heuristic_urls_differ_by_workstream() -> None:
    company = set(heuristic_candidate_urls("Candid Health", "company"))
    team = set(heuristic_candidate_urls("Candid Health", "team"))
    security = set(heuristic_candidate_urls("Candid Health", "security"))
    assert any("linkedin.com" in u for u in team)
    assert not any("linkedin.com" in u for u in security)
    assert any("/security" in u for u in security)
    # Workstreams should not collapse to the identical URL set.
    assert company != team
    assert team != security


def test_serp_detection_and_rank_demotion() -> None:
    article = "https://techcrunch.com/2025/02/12/candid-health-raises/"
    serp = "https://techcrunch.com/?s=Candid+Health"
    bloomberg_serp = "https://www.bloomberg.com/search?query=Candid+Health"
    assert not url_looks_like_serp(article)
    assert url_looks_like_serp(serp)
    assert url_looks_like_serp(bloomberg_serp)
    assert source_rank_score(article) > source_rank_score(serp)


def test_diversify_urls_caps_same_site() -> None:
    raw = [
        "https://www.stripe.com/",
        "https://www.stripe.com/about",
        "https://www.stripe.com/customers",
        "https://www.stripe.com/docs",
        "https://techcrunch.com/2024/01/01/stripe/",
        "https://en.wikipedia.org/wiki/Stripe,_Inc.",
        "https://www.crunchbase.com/organization/stripe",
    ]
    out = diversify_urls(raw, company_name="Stripe", limit=10)
    assert "https://www.stripe.com/" in out or any("stripe.com" in u for u in out)
    stripe_hits = [u for u in out if "stripe.com" in u]
    assert len(stripe_hits) == 1
    domains = {u.split("/")[2].removeprefix("www.") for u in out}
    assert len(domains) >= 3


def test_diversify_urls_prefers_news_over_wiki() -> None:
    raw = [
        "https://en.wikipedia.org/wiki/Stripe",
        "https://www.crunchbase.com/organization/stripe",
        "https://techcrunch.com/2024/01/01/stripe/",
        "https://www.reuters.com/business/stripe",
        "https://stripe.com/",
    ]
    out = diversify_urls(raw, company_name="Stripe", limit=5)
    assert out[0].startswith("https://techcrunch.com") or out[0].startswith(
        "https://www.reuters.com"
    )
    assert "wikipedia.org" not in out[0]
    assert "crunchbase.com" not in out[0]


def test_diversify_prefers_article_over_serp_same_host() -> None:
    raw = [
        "https://techcrunch.com/?s=Stripe",
        "https://www.bloomberg.com/search?query=Stripe",
        "https://techcrunch.com/2024/01/01/stripe-raises/",
        "https://www.reuters.com/business/finance/stripe-story",
    ]
    out = diversify_urls(raw, company_name="Stripe", limit=4)
    assert out[0] == "https://techcrunch.com/2024/01/01/stripe-raises/" or out[
        0
    ].startswith("https://www.reuters.com/business")
    assert not any(url_looks_like_serp(u) for u in out[:2])
