"""Stage 4–5 wiring: screening research helpers, progress FET-safe payload, resolve body."""

from __future__ import annotations

from pathlib import Path

from thesis_api.services.progress_store import sanitize_progress_data
from thesis_api.services.screening_research import corroborate_public_docs
from thesis_api.temporal_app import screening_activities


def test_screening_research_domain_activity_registered() -> None:
    assert callable(screening_activities.screening_research_domain)
    assert screening_activities.screening_research_domain.__name__ == "screening_research_domain"


def test_progress_event_payload_strips_passage_text() -> None:
    """SSE/progress must not leak full evidence passages (sanitize_progress_data)."""
    clean = sanitize_progress_data(
        {
            "status": "completed",
            "claims_total": 2,
            "contradictions_detected": 1,
            "fetched": True,
            "snapshot_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "independent_count": 1,
            "evidence_text": "secret passage that must not stream",
            "passage": "also blocked",
            "prompt": "model prompt",
        }
    )
    assert clean["status"] == "completed"
    assert clean["claims_total"] == 2
    assert clean["fetched"] is True
    assert "evidence_text" not in clean
    assert "passage" not in clean
    assert "prompt" not in clean


def test_evidence_store_module_exists() -> None:
    root = Path(__file__).resolve().parents[1] / "src" / "thesis_api" / "services"
    assert (root / "evidence_store.py").is_file()
    assert (root / "screening_research.py").is_file()


def test_resolve_endpoint_requires_expected_version_in_routes() -> None:
    text = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "thesis_api"
        / "routes"
        / "claims.py"
    ).read_text(encoding="utf-8")
    assert "expected_version" in text
    assert "VERSION_CONFLICT" in text


def test_corroboration_helper_returns_ranked() -> None:
    from thesis_api.services.corroboration import SourceDocument

    out = corroborate_public_docs(
        claim_key="k",
        documents=[
            SourceDocument(
                url="https://a.example/x",
                content_text="Acme robotics raised seed capital in Berlin.",
                search_rank=1,
                is_primary=True,
            ),
            SourceDocument(
                url="https://b.example/y",
                content_text="Unrelated market commentary about weather.",
                search_rank=2,
            ),
        ],
        query_terms=["Acme", "robotics", "Berlin"],
    )
    assert "ranked" in out
    assert out["independent_count"] >= 1
