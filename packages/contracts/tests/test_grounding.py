# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from thesis_contracts.grounding import (
    extract_numeric_facts,
    ground_numeric_statement,
    trust_for_grounding,
)
from thesis_contracts.research import Claim


def test_extract_and_ground_fully() -> None:
    statement = "Acme raised $48 million in 2021 with 200 employees"
    page = "In 2021 Acme raised $48 million and grew to 200 employees worldwide."
    facts = extract_numeric_facts(statement)
    assert "$48 million" in facts or any("48" in f for f in facts)
    g = ground_numeric_statement(statement, page)
    assert g.verdict == "fully_grounded"
    assert g.ok_for_supported
    trust, ver, ctype = trust_for_grounding(g)
    assert trust == "supported"
    assert ver == "verified"
    assert ctype == "metric"


def test_ungrounded_demotes() -> None:
    g = ground_numeric_statement(
        "Notion has a $10 billion valuation and 20 million users",
        "Notion is an all-in-one workspace for notes and docs.",
    )
    assert g.verdict == "ungrounded"
    assert not g.ok_for_supported
    trust, ver, ctype = trust_for_grounding(g)
    assert trust == "insufficient"
    assert ver == "insufficient"
    assert ctype == "metric"


def test_claim_rejects_supported_with_ungrounded_numeric() -> None:
    with pytest.raises(ValueError, match="ungrounded"):
        Claim(
            claim_id=uuid4(),
            assessment_id=uuid4(),
            revision=1,
            domain_id="company",
            statement="Raised $10 billion",
            claim_type="metric",
            subject="funding",
            trust_state="supported",
            evidence_span_ids=[uuid4()],
            snapshot_ids=[uuid4()],
            numeric_facts=["$10 billion"],
            numeric_facts_grounded=[],
            confidence=Decimal("0.7"),
        )


def test_claim_allows_supported_when_grounded() -> None:
    c = Claim(
        claim_id=uuid4(),
        assessment_id=uuid4(),
        revision=1,
        domain_id="company",
        statement="Raised $10 million",
        claim_type="metric",
        subject="funding",
        trust_state="supported",
        verification_status="verified",
        evidence_span_ids=[uuid4()],
        snapshot_ids=[uuid4()],
        numeric_facts=["$10 million"],
        numeric_facts_grounded=["$10 million"],
        confidence=Decimal("0.7"),
    )
    assert c.claim_type == "metric"


def test_claim_rejects_numeric_as_plain_fact() -> None:
    with pytest.raises(ValueError, match="claim_type=metric"):
        Claim(
            claim_id=uuid4(),
            assessment_id=uuid4(),
            revision=1,
            domain_id="company",
            statement="Raised $10 million",
            claim_type="fact",
            subject="funding",
            trust_state="insufficient",
            evidence_span_ids=[uuid4()],
            snapshot_ids=[uuid4()],
            numeric_facts=["$10 million"],
            numeric_facts_grounded=[],
            confidence=Decimal("0.3"),
        )
