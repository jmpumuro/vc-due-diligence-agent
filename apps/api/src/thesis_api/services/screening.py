"""Level 1 screening helpers — public evidence path; no private model calls."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from thesis_api.services.domains import domains_for_level, min_corroborated_for_level
from thesis_api.services.source_quality import (
    has_non_reference_source,
    statement_admits_evidence_gap,
)
from thesis_api.services.sufficiency import evaluate_sufficiency
from thesis_contracts.base import DomainId, GateResult, Level
from thesis_contracts.research import Claim, ContradictionRecord


AGENT_PIPELINE: tuple[str, ...] = (
    "planner",
    "research",
    "verification",
    "evaluation",
    "critic",
    "memo",
)


def plan_domains(level: Level) -> list[DomainId]:
    return domains_for_level(level)


def _supported_source_urls(claims: list[Claim]) -> list[str]:
    urls: list[str] = []
    for c in claims:
        if c.trust_state != "supported":
            continue
        for u in c.source_urls or []:
            if u and u not in urls:
                urls.append(u)
    return urls


def demote_reference_only_sufficient(gate: dict[str, Any], claims: list[Claim]) -> dict[str, Any]:
    """Wiki/Crunchbase alone must not unlock sufficient — need a non-reference source."""
    if gate.get("gate_result") != "sufficient":
        return gate
    urls = _supported_source_urls(claims)
    if has_non_reference_source(urls):
        return gate
    reasons = list(gate.get("reasons") or [])
    reasons.append("reference_sources_only")
    out = dict(gate)
    out["gate_result"] = "partial"
    out["reasons"] = reasons
    # Partial still allows recommendation path at L1; keep allow_recommendation.
    return out


def run_domain_gate(
    *,
    assessment_id: UUID,
    revision: int,
    level: Level,
    domain_id: DomainId,
    claims: list[Claim],
    contradictions: list[ContradictionRecord],
    gate_hint: GateResult | None = None,
) -> dict[str, Any]:
    # Public screening cannot produce diligence-grade financials — mark N/A, not fail.
    hint = gate_hint
    if domain_id == "financials" and hint is None and claims:
        if all(
            c.trust_state == "insufficient" or statement_admits_evidence_gap(c.statement)
            for c in claims
        ):
            hint = "unavailable_at_level"

    decision = evaluate_sufficiency(
        assessment_id=assessment_id,
        revision=revision,
        level=level,
        domain_id=domain_id,
        claims=claims,
        contradictions=contradictions,
        min_corroborated=min_corroborated_for_level(level),
        gate_hint=hint,
    )
    payload = decision.model_dump(mode="json")
    if payload.get("gate_result") == "unavailable_at_level":
        payload["allow_recommendation"] = False
        reasons = list(payload.get("reasons") or [])
        if domain_id == "financials" and "public_financials_unavailable" not in reasons:
            reasons.append("public_financials_unavailable")
        payload["reasons"] = reasons
        return payload
    return demote_reference_only_sufficient(payload, claims)


def build_screening_memo(
    *,
    company_name: str,
    level: Level,
    domain_gates: dict[str, str],
    recommendation: str,
) -> dict[str, Any]:
    """Minimal report/memo payload (ddreport subset) for Level 1."""
    sufficient = sum(1 for g in domain_gates.values() if g == "sufficient")
    return {
        "schema": "ddreport@1-scaffold",
        "company_name": company_name,
        "level": level,
        "recommendation": recommendation,
        "domain_gates": domain_gates,
        "domains_sufficient": sufficient,
        "sections_present": [
            "executive_summary",
            "company_overview",
            "thesis_alignment",
            "team",
            "market",
            "product_technology",
        ],
        "notice": "Automated diligence support; not legal, accounting or investment advice.",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def recommend_from_gates(gates: dict[str, str], *, level: Level) -> str:
    """Map domain gates → memo recommendation with discriminative thresholds.

    - advance: all scored domains sufficient (or N/A)
    - hold: mixed sufficient/partial, or a single insufficiency amid support
    - inconclusive (L1) / pass (L2+): no sufficient support, or multiple insufficiencies
    """
    vals = [g for g in gates.values() if g not in ("not_applicable", "unavailable_at_level")]
    if not vals:
        return "inconclusive"
    n = len(vals)
    suf = sum(1 for g in vals if g == "sufficient")
    insuf = sum(1 for g in vals if g == "insufficient")

    if insuf >= 2 or (insuf >= 1 and suf == 0):
        return "inconclusive" if level == 1 else "pass"
    if insuf >= 1:
        return "hold"
    if suf == n:
        return "advance"
    if suf == 0:
        # All partial — refuse advance; L1 stays inconclusive until sources firm up.
        return "inconclusive" if level == 1 else "hold"
    # Mixed sufficient + partial → hold (not advance).
    return "hold"
