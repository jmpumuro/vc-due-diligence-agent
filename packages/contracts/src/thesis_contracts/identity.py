"""Company identity, assessment identity, and submission policy."""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import Field

from thesis_contracts.base import Level, Strict


class CompanyAlias(Strict):
    value: str
    kind: Literal["name", "domain"]
    source: str
    confidence: Decimal


class CompanyRef(Strict):
    company_id: UUID
    canonical_name: str
    primary_domain: str | None
    aliases: list[CompanyAlias] = []


class AssessmentIdentity(Strict):
    firm_id: UUID
    company_id: UUID
    assessment_id: UUID
    mandate_id: UUID
    config_snapshot_id: UUID
    revision: int = Field(ge=1)
    trigger: Literal[
        "manual",
        "discovery",
        "monitoring",
        "reassessment",
        "upgrade",
        "new_evidence",
    ]
    level: Level


class SubmissionPolicy(str, Enum):
    REUSE_ACTIVE = "reuse_active"
    NEW_ASSESSMENT = "new_assessment"
    REASSESS_LATEST = "reassess_latest"


class IdentityCandidate(Strict):
    company_id: UUID | None = None
    canonical_name: str
    primary_domain: str | None = None
    confidence: Decimal
    match_reasons: list[str] = []


class SubmitCompanyResponse(Strict):
    company: CompanyRef
    assessment_id: UUID
    outcome: Literal[
        "created",
        "reused_active",
        "reassessment_created",
        "identity_review_required",
    ]
    identity_candidates: list[IdentityCandidate] = []
    identity_request_id: UUID | None = None
