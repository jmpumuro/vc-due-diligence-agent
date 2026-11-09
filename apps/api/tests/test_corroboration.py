"""Corroboration: relevance ≠ independence; syndication ≠ confirmation."""

from __future__ import annotations

from thesis_api.services.corroboration import (
    SourceDocument,
    rank_and_corroborate,
)


def test_syndicated_copies_not_independent() -> None:
    text = "Acme announced a Series B of forty million dollars today in San Francisco."
    result = rank_and_corroborate(
        claim_key="series_b",
        documents=[
            SourceDocument(url="https://news-a.example/1", content_text=text, search_rank=1),
            SourceDocument(url="https://news-b.example/1", content_text=text, search_rank=2),
            SourceDocument(
                url="https://blog.example/opinion",
                content_text="Unrelated opinion piece about markets.",
                search_rank=3,
            ),
        ],
        query_terms=["series", "b", "forty", "million"],
    )
    # Near-duplicate syndication collapses independence
    assert result.independent_count < 3
    assert result.syndicated_groups or any(r.near_duplicate_of for r in result.ranked)


def test_high_rank_not_automatic_credibility() -> None:
    result = rank_and_corroborate(
        claim_key="x",
        documents=[
            SourceDocument(
                url="https://spam.example/1",
                title="buy now",
                content_text="buy now",
                search_rank=1,
                company_authored=True,
            ),
        ],
        query_terms=["buy"],
    )
    assert result.ranked[0].relevance > 0
    assert result.ranked[0].evidence_quality == "weak"
    assert result.independent_count < 2


def test_contradictory_source_preserved() -> None:
    result = rank_and_corroborate(
        claim_key="arr",
        documents=[
            SourceDocument(
                url="https://deck.example/",
                content_text="ARR is 10 million",
                search_rank=1,
                company_authored=True,
            ),
            SourceDocument(
                url="https://filing.example/",
                content_text="Revenue was 2 million",
                search_rank=9,
                is_primary=True,
            ),
        ],
        query_terms=["ARR", "revenue"],
        contradictory_urls=["https://filing.example/"],
    )
    preserved = [r for r in result.ranked if r.preserve_despite_low_relevance]
    assert preserved
    assert "filing.example" in preserved[0].canonical_url
