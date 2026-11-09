"""P0 research-quality foundations: identity, lineage, contradictions, sufficiency, VoI."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from thesis_api.services.contradictions import build_contradiction, mark_claims_contested
from thesis_api.services.entity_resolution import resolve_identity
from thesis_api.services.evidence_lineage import check_claim_lineage
from thesis_api.services.screening import demote_reference_only_sufficient
from thesis_api.services.search.normalize import canonicalize_url, dedupe_results_by_url
from thesis_api.services.source_quality import (
    has_non_reference_source,
    identity_evidence_is_thin,
    statement_admits_evidence_gap,
)
from thesis_api.services.sufficiency import evaluate_sufficiency
from thesis_api.services.voi_planner import plan_voi_actions
from thesis_contracts.provenance import EvidenceSpan
from thesis_contracts.research import Claim, ResolvedIdentityCandidate


def test_similar_names_different_domains_are_ambiguous() -> None:
    known = [
        ResolvedIdentityCandidate(
            company_id=uuid4(),
            canonical_name="Acme Robotics",
            primary_domain="acme-robotics.com",
            confidence=Decimal("1"),
        ),
        ResolvedIdentityCandidate(
            company_id=uuid4(),
            canonical_name="Acme Robotics",
            primary_domain="acmerobotics.io",
            confidence=Decimal("1"),
        ),
    ]
    result = resolve_identity(
        query_name="Acme Robotics Inc",
        query_domain="acme-robotics.com",
        known=known,
    )
    assert result.outcome in ("matched", "ambiguous")
    # Querying without domain against two same-named firms must not silently merge.
    amb = resolve_identity(query_name="Acme Robotics", query_domain=None, known=known)
    assert amb.outcome == "ambiguous"
    assert amb.review_required


def test_domain_exact_match() -> None:
    cid = uuid4()
    known = [
        ResolvedIdentityCandidate(
            company_id=cid,
            canonical_name="Lattice Grid",
            primary_domain="latticegrid.io",
            confidence=Decimal("1"),
        )
    ]
    result = resolve_identity(
        query_name="Lattice Grid GmbH",
        query_domain="https://www.latticegrid.io/about",
        known=known,
    )
    assert result.outcome == "matched"
    assert result.selected and result.selected.company_id == cid


def test_claim_lineage_requires_spans_and_snapshots() -> None:
    snap = uuid4()
    span_id = uuid4()
    claim = Claim(
        claim_id=uuid4(),
        assessment_id=uuid4(),
        revision=1,
        domain_id="company",
        statement="HQ in Berlin",
        subject="company",
        trust_state="supported",
        evidence_span_ids=[span_id],
        snapshot_ids=[snap],
    )
    span = EvidenceSpan(
        span_id=span_id,
        snapshot_id=snap,
        start=0,
        end=12,
        text="HQ in Berlin",
        text_sha256="a" * 64,
    )
    ok = check_claim_lineage(claim, {span_id: span}, known_snapshot_ids={snap})
    assert ok.ok
    bad = check_claim_lineage(claim, {}, known_snapshot_ids={snap})
    assert not bad.ok
    assert any(m.startswith("span:") for m in bad.missing)


def test_contradictions_preserved_and_contest_claims() -> None:
    a = Claim(
        claim_id=uuid4(),
        assessment_id=uuid4(),
        revision=1,
        domain_id="traction",
        statement="ARR $10M",
        subject="arr",
        trust_state="supported",
        evidence_span_ids=[uuid4()],
        snapshot_ids=[uuid4()],
        company_authored=True,
    )
    b = a.model_copy(
        update={
            "claim_id": uuid4(),
            "statement": "ARR $2M",
            "company_authored": False,
            "evidence_span_ids": [uuid4()],
            "snapshot_ids": [uuid4()],
        }
    )
    rec = build_contradiction(
        assessment_id=a.assessment_id,
        revision=1,
        claims=[a, b],
        explanation="Deck ARR conflicts with filing",
    )
    assert rec.resolution == "open"
    assert len(rec.claim_ids) == 2
    contested = mark_claims_contested([a, b])
    assert all(c.trust_state == "contested" for c in contested)


def test_reference_only_sources_demote_sufficient() -> None:
    assert has_non_reference_source(["https://en.wikipedia.org/wiki/Stripe"]) is False
    assert has_non_reference_source(
        ["https://en.wikipedia.org/wiki/Stripe", "https://stripe.com/"]
    )
    assert identity_evidence_is_thin(
        source_urls=["https://en.wikipedia.org/wiki/Stripe", "https://www.crunchbase.com/organization/stripe"],
        company_name="Stripe",
    )
    assert not identity_evidence_is_thin(
        source_urls=["https://stripe.com/", "https://en.wikipedia.org/wiki/Stripe"],
        company_name="Stripe",
    )
    aid = uuid4()
    span = uuid4()
    snap = uuid4()
    claim = Claim(
        claim_id=uuid4(),
        firm_id="firm",
        assessment_id=aid,
        revision=1,
        domain_id="company",
        statement="Stripe processes payments.",
        subject="company",
        trust_state="supported",
        verification_status="extracted",
        confidence=Decimal("0.7"),
        evidence_quality="mixed",
        evidence_span_ids=[span],
        snapshot_ids=[snap],
        source_urls=["https://en.wikipedia.org/wiki/Stripe", "https://www.crunchbase.com/organization/stripe"],
        company_authored=False,
        extracted_at=datetime.now(timezone.utc),
    )
    demoted = demote_reference_only_sufficient(
        {"gate_result": "sufficient", "reasons": [], "allow_recommendation": True},
        [claim],
    )
    assert demoted["gate_result"] == "partial"
    assert "reference_sources_only" in demoted["reasons"]
    assert statement_admits_evidence_gap(
        "Public team identity is not evidenced on the cited pages."
    )
    assert not statement_admits_evidence_gap(
        "Stripe is a financial infrastructure company headquartered in the US."
    )


def test_sufficiency_blocks_insufficient_recommendation() -> None:
    aid = uuid4()
    decision = evaluate_sufficiency(
        assessment_id=aid,
        revision=1,
        level=2,
        domain_id="traction",
        claims=[],
        contradictions=[],
        min_corroborated=2,
    )
    assert decision.gate_result == "insufficient"
    assert decision.allow_recommendation is False
    with pytest.raises(Exception):
        from thesis_contracts.research import SufficiencyDecision

        SufficiencyDecision.model_validate(
            {**decision.model_dump(mode="json"), "allow_recommendation": True}
        )


def test_l2_sufficiency_counts_independent_domains_not_claim_rows() -> None:
    """One claim citing company.com + reuters.com should clear L2 min_corroborated=2."""
    from thesis_api.services.screening import run_domain_gate

    aid = uuid4()
    claim = Claim(
        claim_id=uuid4(),
        firm_id="firm",
        assessment_id=aid,
        revision=1,
        domain_id="traction",
        statement="Acme reports 200 enterprise customers.",
        subject="traction",
        trust_state="supported",
        verification_status="extracted",
        confidence=Decimal("0.7"),
        evidence_quality="mixed",
        evidence_span_ids=[uuid4(), uuid4()],
        snapshot_ids=[uuid4(), uuid4()],
        source_urls=["https://acme.com/customers", "https://www.reuters.com/acme-customers"],
        company_authored=False,
        extracted_at=datetime.now(timezone.utc),
    )
    decision = evaluate_sufficiency(
        assessment_id=aid,
        revision=1,
        level=2,
        domain_id="traction",
        claims=[claim],
        contradictions=[],
        min_corroborated=2,
    )
    assert decision.gate_result == "sufficient"
    assert decision.corroborated_claims >= 2

    # Wiki alone must not clear L2 even with two claim rows of the same domain.
    thin = Claim(
        claim_id=uuid4(),
        firm_id="firm",
        assessment_id=aid,
        revision=1,
        domain_id="traction",
        statement="Acme exists.",
        subject="traction",
        trust_state="supported",
        verification_status="extracted",
        confidence=Decimal("0.5"),
        evidence_quality="weak",
        evidence_span_ids=[uuid4()],
        snapshot_ids=[uuid4()],
        source_urls=["https://en.wikipedia.org/wiki/Acme"],
        company_authored=False,
        extracted_at=datetime.now(timezone.utc),
    )
    thin_gate = run_domain_gate(
        assessment_id=aid,
        revision=1,
        level=2,
        domain_id="traction",
        claims=[thin],
        contradictions=[],
    )
    assert thin_gate["gate_result"] in ("insufficient", "partial")


def test_financials_gap_is_unavailable_at_level() -> None:
    from thesis_api.services.screening import run_domain_gate

    aid = uuid4()
    claim = Claim(
        claim_id=uuid4(),
        firm_id="firm",
        assessment_id=aid,
        revision=1,
        domain_id="financials",
        statement="Public financial metrics are not evidenced on the cited pages.",
        subject="financials",
        trust_state="insufficient",
        verification_status="insufficient",
        confidence=Decimal("0.3"),
        evidence_quality="weak",
        evidence_span_ids=[uuid4()],
        snapshot_ids=[uuid4()],
        source_urls=["https://acme.com/"],
        company_authored=False,
        extracted_at=datetime.now(timezone.utc),
    )
    gate = run_domain_gate(
        assessment_id=aid,
        revision=1,
        level=3,
        domain_id="financials",
        claims=[claim],
        contradictions=[],
    )
    assert gate["gate_result"] == "unavailable_at_level"
    assert gate["allow_recommendation"] is False


def test_voi_prioritizes_contradictions_and_bounds() -> None:
    aid = uuid4()
    actions = plan_voi_actions(
        assessment_id=aid,
        domain_gates={
            "traction": "insufficient",
            "market": "partial",
            "team": "sufficient",
        },
        unanswered_questions={
            "traction": ["Independent ARR proof?", "Logo retention?"],
            "market": ["TAM source?"],
            "team": [],
        },
        open_contradiction_domains={"traction"},
        budget_usd_remaining=Decimal("5"),
    )
    assert actions
    assert actions[0].domain_id == "traction"
    assert actions[0].blocking_gate
    assert len(actions) <= 12


def test_url_canonicalize_and_dedupe() -> None:
    assert canonicalize_url("https://WWW.Example.com/path/?utm_source=x") == "https://example.com/path"
    rows = dedupe_results_by_url(
        [
            {"url": "https://example.com/a?utm_campaign=1"},
            {"url": "https://www.example.com/a"},
            {"url": "https://other.com/b"},
        ]
    )
    assert len(rows) == 2
