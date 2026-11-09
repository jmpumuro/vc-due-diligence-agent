# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from thesis_api.services.assessment_view import (
    public_dataroom_from_claims,
    public_financials_from_claims,
    requests_from_assessment,
    risks_from_assessment,
)
from thesis_contracts.research import Claim


def _claim(**kwargs: object) -> Claim:
    base = dict(
        claim_id=uuid4(),
        assessment_id=uuid4(),
        revision=1,
        domain_id="company",
        statement="Acme raised $10 million Series A",
        subject="funding",
        trust_state="supported",
        evidence_span_ids=[uuid4()],
        snapshot_ids=[uuid4()],
        source_urls=["https://www.acme.com/about"],
        company_authored=False,
        confidence=Decimal("0.7"),
    )
    base.update(kwargs)
    return Claim(**base)  # type: ignore[arg-type]


def test_public_dataroom_groups_urls() -> None:
    claims = [
        _claim(),
        _claim(
            domain_id="product",
            statement="Acme ships a product",
            source_urls=["https://www.acme.com/about", "https://example.com/x"],
        ),
    ]
    room = public_dataroom_from_claims(claims, level=1)
    assert room["mode"] == "public_evidence"
    assert room["document_count"] == 1  # example.com filtered
    assert room["documents"][0]["claim_count"] == 2


def test_public_financials_signals_and_metrics() -> None:
    claims = [
        _claim(),
        _claim(domain_id="team", statement="Leadership is experienced", source_urls=[]),
        _claim(
            domain_id="product",
            statement="Collaborative tool allows multiple users to edit",
            source_urls=["https://news.example.org/x"],
        ),
    ]
    fin = public_financials_from_claims(claims, level=1, domain_gates={})
    assert fin["signal_count"] == 1
    assert fin["metrics"] == []
    assert fin["public_signals"][0]["validated"] is False
    assert "ARR" not in fin["notice"] or "No ARR/burn" in fin["notice"]

    fin_l3 = public_financials_from_claims(claims, level=3, domain_gates={})
    assert fin_l3["metrics"][0]["metric"] == "ARR"
    assert fin_l3["metrics"][0]["status"] == "awaiting_workbook"


def test_risks_and_asks_link_agent_findings() -> None:
    claims = [
        _claim(
            domain_id="team",
            statement="Public team identity is not evidenced on the cited pages.",
            trust_state="insufficient",
            source_urls=[
                "https://techcrunch.com/x",
                "https://www.linkedin.com/in/y",
            ],
        ),
        _claim(
            domain_id="market",
            statement="Market positioning not evidenced.",
            trust_state="insufficient",
            source_urls=["https://www.reuters.com/a"],
        ),
    ]
    risks = risks_from_assessment(
        domain_gates={"team": "insufficient", "market": "insufficient", "company": "sufficient"},
        open_contradictions=0,
        company_name="Figma",
        claims=claims,
    )
    assert {r["id"] for r in risks} == {"insuff-market", "insuff-team"}
    team = next(r for r in risks if r["id"] == "insuff-team")
    assert "Public team identity" in team["detail"]
    assert "techcrunch.com" in team["source_hosts"]
    assert team["claim_ids"]
    assert team["likelihood"] == "high"
    assert "Do not treat this domain as verified" not in team["detail"]

    asks = requests_from_assessment(
        domain_gates={"team": "insufficient"}, level=1, claims=claims
    )
    assert asks[0]["claim_ids"]
    assert "Public team identity" in asks[0]["detail"]
