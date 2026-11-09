"""Research-quality contracts: claims, lineage, contradictions, sufficiency, VoI, progress.

Inspired by FirstSignal entity/claim/contradiction shapes (ideas only — no licence on that
repo) and GPT-Researcher / II-Researcher planning & progress patterns (Apache-2.0).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from thesis_contracts.base import DomainId, GateResult, Level, Strict

TrustState = Literal["supported", "contested", "unsupported", "stale", "insufficient"]
IdentityMatchKind = Literal["exact_domain", "exact_name", "alias", "fuzzy_name", "registry_id"]


class FounderRef(Strict):
    founder_id: UUID
    display_name: str
    aliases: list[str] = []
    linkedin_url: str | None = None
    github_login: str | None = None


class IdentitySignal(Strict):
    kind: IdentityMatchKind
    value: str
    weight: Decimal = Field(ge=0, le=1)
    source: str


class ResolvedIdentityCandidate(Strict):
    company_id: UUID | None = None
    canonical_name: str
    primary_domain: str | None = None
    founders: list[FounderRef] = []
    signals: list[IdentitySignal] = []
    confidence: Decimal = Field(ge=0, le=1)
    ambiguous: bool = False


class IdentityResolution(Strict):
    """Outcome of company/founder resolution. Names alone never force a merge."""

    query_name: str
    query_domain: str | None = None
    outcome: Literal["matched", "created", "ambiguous", "rejected"]
    selected: ResolvedIdentityCandidate | None = None
    candidates: list[ResolvedIdentityCandidate] = []
    review_required: bool = False
    reason: str | None = None

    @model_validator(mode="after")
    def _rules(self) -> IdentityResolution:
        if self.outcome == "ambiguous" and not self.review_required:
            raise ValueError("ambiguous identity requires review_required=True")
        if self.outcome == "matched" and self.selected is None:
            raise ValueError("matched requires selected candidate")
        if self.selected and self.selected.ambiguous and self.outcome == "matched":
            raise ValueError("cannot auto-match an ambiguous candidate")
        return self


ClaimType = Literal[
    "fact",
    "metric",
    "relationship",
    "status",
    "quote",
    "inference",
    "other",
]


class Claim(Strict):
    """Atomic assertion with mandatory evidence lineage."""

    claim_id: UUID
    firm_id: str | None = None
    assessment_id: UUID
    company_id: UUID | None = None
    revision: int = Field(ge=1)
    domain_id: DomainId
    statement: str
    claim_type: ClaimType = "fact"
    subject: str
    predicate: str | None = None
    object: str | None = None
    trust_state: TrustState
    verification_status: Literal[
        "extracted", "verified", "contested", "rejected", "insufficient"
    ] = "extracted"
    confidence: Decimal = Field(default=Decimal("0.5"), ge=0, le=1)
    evidence_quality: Literal["strong", "good", "mixed", "weak"] = "mixed"
    evidence_span_ids: list[UUID] = Field(min_length=1)
    snapshot_ids: list[UUID] = Field(min_length=1)
    supporting_claim_ids: list[UUID] = []
    contradicting_claim_ids: list[UUID] = []
    source_urls: list[str] = []
    # Numeric facts extracted from statement; grounded_* must cover them when supported.
    numeric_facts: list[str] = []
    numeric_facts_grounded: list[str] = []
    company_authored: bool = False
    schema_version: int = 1
    extracted_at: datetime | None = None

    @model_validator(mode="after")
    def _lineage(self) -> Claim:
        if self.trust_state == "supported" and not self.evidence_span_ids:
            raise ValueError("supported claims need evidence spans")
        if self.numeric_facts and self.claim_type not in ("metric", "inference"):
            raise ValueError("numeric_facts require claim_type=metric (or inference)")
        if self.trust_state == "supported" and self.numeric_facts:
            missing = [f for f in self.numeric_facts if f not in self.numeric_facts_grounded]
            if missing:
                raise ValueError(
                    "supported claims cannot leave numeric facts ungrounded: "
                    + ", ".join(missing)
                )
            if self.verification_status not in ("verified", "extracted"):
                raise ValueError("supported numeric claims need verified/extracted status")
        return self


ContradictionType = Literal[
    "numeric_mismatch",
    "status_conflict",
    "timeline_conflict",
    "entity_conflict",
    "source_conflict",
    "other",
]


class ContradictionRecord(Strict):
    """Conflicting claims are preserved — never silently collapsed."""

    contradiction_id: UUID
    firm_id: str | None = None
    assessment_id: UUID
    revision: int = Field(ge=1)
    domain_ids: list[DomainId]
    claim_ids: list[UUID] = Field(min_length=2)
    contradiction_type: ContradictionType = "other"
    severity: Literal["low", "medium", "high", "critical"]
    explanation: str
    evidence_for: list[UUID] = []  # span ids
    evidence_against: list[UUID] = []
    resolution: Literal["open", "accepted_risk", "resolved_with_private", "waived"] = "open"
    human_review_state: Literal["none", "pending", "in_review", "decided"] = "none"
    trust_impact: TrustState = "contested"
    version: int = 1  # optimistic concurrency for human resolution
    schema_version: int = 1


class ContradictionResolutionEvent(Strict):
    event_id: UUID
    contradiction_id: UUID
    from_resolution: str
    to_resolution: str
    actor_user_id: UUID
    comment: str | None = None
    expected_version: int
    at: datetime



class EvidenceLineageCheck(Strict):
    claim_id: UUID
    ok: bool
    missing: list[str] = []
    detail: str | None = None


class SufficiencyDecision(Strict):
    """Blocks unsupported investment conclusions when gates fail."""

    assessment_id: UUID
    revision: int
    level: Level
    domain_id: DomainId
    gate_result: GateResult
    material_claims: int
    corroborated_claims: int
    open_contradictions: int
    allow_recommendation: bool
    reasons: list[str] = []

    @model_validator(mode="after")
    def _block(self) -> SufficiencyDecision:
        if self.gate_result in ("insufficient", "unavailable_at_level") and self.allow_recommendation:
            raise ValueError("insufficient evidence cannot allow_recommendation")
        return self


class VoIAction(Strict):
    """Value-of-information next research step (Planner input)."""

    action_id: UUID
    assessment_id: UUID
    domain_id: DomainId
    question: str
    expected_decision_impact: Decimal = Field(ge=0, le=1)
    cost_estimate_usd: Decimal = Field(ge=0)
    rationale: str
    blocking_gate: bool = False


class ResearchProgressEvent(Strict):
    """Typed progress for SSE / UI (II-Researcher-style event envelope, Thesis names)."""

    event_type: Literal[
        "assessment.status",
        "domain.status",
        "verification.progress",
        "evidence.missing",
        "evidence.sufficiency",
        "contradiction.detected",
        "retrieval.progress",
        "search.degraded",
        "provider.failure",
        "human_review",
        "partial_results",
        "error",
        "stage",
    ]
    assessment_id: UUID
    revision: int
    domain_id: DomainId | None = None
    message: str
    data: dict = {}
    occurred_at: datetime
