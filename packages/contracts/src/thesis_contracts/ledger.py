"""External operation ledger — at-least-once provider calls with compare-and-set states."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import Field

from thesis_contracts.base import Strict

LedgerStatus = Literal[
    "RESERVED",
    "IN_FLIGHT",
    "SUCCEEDED",
    "FAILED",
    "UNKNOWN",
    "RECONCILED",
]

CostCertainty = Literal["actual", "estimated", "unknown"]

ALLOWED_LEDGER_TRANSITIONS: dict[LedgerStatus, frozenset[LedgerStatus]] = {
    "RESERVED": frozenset({"IN_FLIGHT", "FAILED"}),
    "IN_FLIGHT": frozenset({"SUCCEEDED", "FAILED", "UNKNOWN"}),
    "SUCCEEDED": frozenset(),
    "FAILED": frozenset({"IN_FLIGHT"}),  # retryable failure, same operation_id
    "UNKNOWN": frozenset({"RECONCILED", "IN_FLIGHT"}),
    "RECONCILED": frozenset(),
}


class LedgerTransitionError(ValueError):
    pass


class ExternalOperation(Strict):
    operation_id: UUID
    firm_id: UUID
    assessment_id: UUID | None = None
    activity_type: str
    input_hash: str = Field(min_length=16)
    provider: str
    status: LedgerStatus
    attempt_count: int = Field(ge=0)
    reservation_id: UUID | None = None
    provider_request_id: str | None = None
    result_ref: str | None = None
    actual_cost: Decimal | None = None
    estimated_cost: Decimal | None = None
    cost_certainty: CostCertainty | None = None
    last_error: str | None = None
    possible_duplicate_spend: bool = False
    lease_expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


def can_transition_ledger(current: LedgerStatus, nxt: LedgerStatus) -> bool:
    return nxt in ALLOWED_LEDGER_TRANSITIONS.get(current, frozenset())


def transition_ledger(current: LedgerStatus, nxt: LedgerStatus) -> LedgerStatus:
    if not can_transition_ledger(current, nxt):
        raise LedgerTransitionError(f"illegal ledger transition {current} → {nxt}")
    return nxt
