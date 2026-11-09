"""Contradiction tracking — preserve conflicts; never silent resolve."""

from __future__ import annotations

from uuid import UUID, uuid4

from thesis_contracts.research import Claim, ContradictionRecord


def build_contradiction(
    *,
    assessment_id: UUID,
    revision: int,
    claims: list[Claim],
    explanation: str,
    severity: str = "high",
) -> ContradictionRecord:
    if len(claims) < 2:
        raise ValueError("contradiction needs at least two claims")
    domains = sorted({c.domain_id for c in claims})
    return ContradictionRecord(
        contradiction_id=uuid4(),
        assessment_id=assessment_id,
        revision=revision,
        domain_ids=domains,  # type: ignore[arg-type]
        claim_ids=[c.claim_id for c in claims],
        severity=severity,  # type: ignore[arg-type]
        explanation=explanation,
        evidence_for=list(claims[0].evidence_span_ids),
        evidence_against=[sid for c in claims[1:] for sid in c.evidence_span_ids],
        resolution="open",
        trust_impact="contested",
    )


def mark_claims_contested(claims: list[Claim]) -> list[Claim]:
    """Return new claim objects with trust_state contested (immutable models)."""
    out: list[Claim] = []
    for c in claims:
        out.append(c.model_copy(update={"trust_state": "contested"}))
    return out


def open_contradiction_count(records: list[ContradictionRecord]) -> int:
    return sum(1 for r in records if r.resolution == "open")
