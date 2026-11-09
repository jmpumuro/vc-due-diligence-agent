"""Atomic hierarchical budget reservations (P0-03)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import Field

from thesis_contracts.base import Strict

BudgetLevelKind = Literal[
    "agent_invocation",
    "research_task",
    "assessment",
    "tenant_day",
    "provider",
]
BudgetReservationStatus = Literal["held", "settled", "released", "expired", "reclaimed"]

ALLOWED_BUDGET_TRANSITIONS: dict[BudgetReservationStatus, frozenset[BudgetReservationStatus]] = {
    "held": frozenset({"settled", "released", "expired", "reclaimed"}),
    "settled": frozenset(),
    "released": frozenset(),
    "expired": frozenset({"reclaimed"}),
    "reclaimed": frozenset(),
}


class Spend(Strict):
    usd: Decimal = Field(ge=0)
    input_tokens: int = Field(ge=0, default=0)
    output_tokens: int = Field(ge=0, default=0)
    tool_calls: int = Field(ge=0, default=0)
    elapsed_s: Decimal = Field(ge=0, default=Decimal("0"))


class BudgetLevelRef(Strict):
    kind: BudgetLevelKind
    key: str  # e.g. firm_id, assessment_id, provider name
    limit_usd: Decimal = Field(ge=0)


class BudgetReservation(Strict):
    reservation_id: UUID
    operation_id: UUID
    levels: list[BudgetLevelRef]
    reserved: Spend
    settled: Spend | None = None
    status: BudgetReservationStatus
    lease_expires_at: datetime


def can_transition_budget(
    current: BudgetReservationStatus, nxt: BudgetReservationStatus
) -> bool:
    return nxt in ALLOWED_BUDGET_TRANSITIONS.get(current, frozenset())
