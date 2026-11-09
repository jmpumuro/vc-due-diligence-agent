"""Version-bound human review target."""

from __future__ import annotations

import hashlib
import json
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from thesis_contracts.base import Strict


class ReviewTarget(Strict):
    assessment_id: UUID
    assessment_revision: int = Field(ge=1)
    evidence_snapshot_id: UUID
    evaluation_id: UUID
    memo_version_id: UUID  # holds report_version_id (compatibility name)
    review_policy_version: str


def target_digest(target: ReviewTarget) -> str:
    """SHA-256 of canonical JSON (sorted keys, UUID as str)."""
    payload = target.model_dump(mode="json")
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


class SubmitReviewRequest(Strict):
    target: ReviewTarget
    decision: Literal["approve", "reject", "request_research", "request_information"]
    comment: str | None = None
    requested_items: list[str] = []
    idempotency_key: str

    @model_validator(mode="after")
    def _items(self) -> SubmitReviewRequest:
        if self.decision == "request_information" and not self.requested_items:
            raise ValueError("request_information needs requested_items")
        return self
