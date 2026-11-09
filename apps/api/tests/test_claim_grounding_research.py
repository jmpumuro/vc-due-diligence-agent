# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from uuid import uuid4

from thesis_api.services.screening_research import claim_from_evidence


def test_claim_from_evidence_demotes_ungrounded_numeric() -> None:
    claim = claim_from_evidence(
        firm_id="frm_demo",
        assessment_id=uuid4(),
        revision=1,
        domain_id="market",
        statement="Figma has 4 million users and a $10 billion valuation.",
        subject="market",
        snapshot_id=str(uuid4()),
        span_id=str(uuid4()),
        source_url="https://www.figma.com/about/",
        passage="Figma helps teams design products together in the browser.",
        apply_grounding=True,
    )
    assert claim.trust_state == "insufficient"
    assert claim.verification_status == "insufficient"
    assert claim.claim_type == "metric"
    assert claim.numeric_facts
    assert claim.numeric_facts_grounded == []
    assert "missing on cited passage" in claim.statement


def test_claim_from_evidence_keeps_qualitative_supported() -> None:
    claim = claim_from_evidence(
        firm_id="frm_demo",
        assessment_id=uuid4(),
        revision=1,
        domain_id="product",
        statement="SonderMind connects people with licensed therapists via telehealth.",
        subject="product",
        snapshot_id=str(uuid4()),
        span_id=str(uuid4()),
        source_url="https://www.sondermind.com/about-us/",
        passage="SonderMind telehealth therapy with licensed therapists for mental health care.",
        apply_grounding=True,
    )
    assert claim.trust_state == "supported"
    assert claim.numeric_facts == []
