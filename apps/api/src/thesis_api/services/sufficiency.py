"""Evidence sufficiency — refuse unsupported investment conclusions."""

from __future__ import annotations

from uuid import UUID

from thesis_api.services.contradictions import open_contradiction_count
from thesis_api.services.source_quality import (
    REFERENCE_ONLY_DOMAINS,
    source_domains_from_urls,
)
from thesis_contracts.base import DomainId, GateResult, Level
from thesis_contracts.research import Claim, ContradictionRecord, SufficiencyDecision


def independent_evidence_units(claims: list[Claim]) -> int:
    """Count distinct non-reference source domains across supported claims.

    L2+ "corroboration" means independent public sources — not claim row count.
    A single well-sourced claim with company.com + reuters.com counts as 2.
    """
    domains: set[str] = set()
    for c in claims:
        if c.trust_state != "supported" or c.company_authored:
            continue
        if not (c.evidence_span_ids or c.snapshot_ids):
            continue
        for d in source_domains_from_urls(list(c.source_urls or [])):
            if d not in REFERENCE_ONLY_DOMAINS:
                domains.add(d)
        # Snapshots without parseable URLs still count as weak units (≤1 each claim).
        if not source_domains_from_urls(list(c.source_urls or [])):
            domains.add(f"snap:{c.claim_id}")
    return len(domains)


def evaluate_sufficiency(
    *,
    assessment_id: UUID,
    revision: int,
    level: Level,
    domain_id: DomainId,
    claims: list[Claim],
    contradictions: list[ContradictionRecord],
    min_corroborated: int,
    gate_hint: GateResult | None = None,
) -> SufficiencyDecision:
    material = [c for c in claims if c.trust_state in ("supported", "contested")]
    supported = [
        c
        for c in material
        if c.trust_state == "supported"
        and not c.company_authored
        and (len(c.evidence_span_ids) >= 1 or len(c.snapshot_ids) >= 1)
    ]
    units = independent_evidence_units(supported)
    # Keep claim-row count for diagnostics; gate on independent units at L2+.
    corroborated_n = units if level >= 2 else len(supported)

    open_c = open_contradiction_count(
        [x for x in contradictions if domain_id in x.domain_ids or not x.domain_ids]
    )
    reasons: list[str] = []
    if corroborated_n < min_corroborated:
        reasons.append(
            f"independent_sources {corroborated_n} < {min_corroborated}"
            if level >= 2
            else f"corroborated_claims {corroborated_n} < {min_corroborated}"
        )
    if open_c:
        reasons.append(f"open_contradictions={open_c}")
    # Gap-admission claims alone should not poison a domain that also has supported evidence.
    only_gaps = bool(claims) and not supported and any(
        c.trust_state == "insufficient" for c in claims
    )
    if only_gaps:
        reasons.append("claims_marked_insufficient")

    if gate_hint is not None:
        gate = gate_hint
    elif not reasons:
        gate = "sufficient"
    elif corroborated_n == 0:
        gate = "insufficient"
    else:
        gate = "partial"

    allow = gate in ("sufficient", "partial", "not_applicable")
    # Never allow a firm recommendation path on insufficient / unavailable.
    if gate in ("insufficient", "unavailable_at_level"):
        allow = False

    return SufficiencyDecision(
        assessment_id=assessment_id,
        revision=revision,
        level=level,
        domain_id=domain_id,
        gate_result=gate,
        material_claims=len(material),
        corroborated_claims=corroborated_n,
        open_contradictions=open_c,
        allow_recommendation=allow,
        reasons=reasons,
    )
