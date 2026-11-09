# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Thesis contributors
"""Assessment lifecycle state machine.

Canonical states come from the master plan / agent contracts. Transitions are
enforced here and later mirrored by a PostgreSQL check constraint.
"""

from __future__ import annotations

from typing import Literal

AssessmentState = Literal[
    "CREATED",
    "PLANNING",
    "RESEARCHING",
    "VALIDATING",
    "EVALUATING",
    "CRITIQUING",
    "MEMO_READY",
    "AWAITING_REVIEW",
    "INFORMATION_REQUESTED",
    "DELIVERING",
    "COMPLETED",
    "REJECTED",
    "BLOCKED_CONFIGURATION",
    "BUDGET_EXHAUSTED",
    "CANCELLED",
    "FAILED",
]

# Happy-path spine plus documented branches (review, info requests, exceptions).
ALLOWED_TRANSITIONS: dict[AssessmentState, frozenset[AssessmentState]] = {
    "CREATED": frozenset({"PLANNING", "CANCELLED", "FAILED", "BLOCKED_CONFIGURATION"}),
    "PLANNING": frozenset(
        {"RESEARCHING", "CANCELLED", "FAILED", "BLOCKED_CONFIGURATION", "BUDGET_EXHAUSTED"}
    ),
    "RESEARCHING": frozenset(
        {
            "VALIDATING",
            "CANCELLED",
            "FAILED",
            "BLOCKED_CONFIGURATION",
            "BUDGET_EXHAUSTED",
        }
    ),
    "VALIDATING": frozenset(
        {
            "EVALUATING",
            "RESEARCHING",  # follow-up research after evidence freeze gaps
            "CANCELLED",
            "FAILED",
            "BLOCKED_CONFIGURATION",
            "BUDGET_EXHAUSTED",
        }
    ),
    "EVALUATING": frozenset(
        {"CRITIQUING", "CANCELLED", "FAILED", "BLOCKED_CONFIGURATION", "BUDGET_EXHAUSTED"}
    ),
    "CRITIQUING": frozenset(
        {
            "MEMO_READY",
            "RESEARCHING",  # capped critic follow-up
            "CANCELLED",
            "FAILED",
            "BLOCKED_CONFIGURATION",
            "BUDGET_EXHAUSTED",
        }
    ),
    "MEMO_READY": frozenset(
        {
            "AWAITING_REVIEW",
            "REJECTED",  # out_of_mandate auto-route with audit
            "CANCELLED",
            "FAILED",
        }
    ),
    "AWAITING_REVIEW": frozenset(
        {
            "DELIVERING",
            "REJECTED",
            "INFORMATION_REQUESTED",
            "EVALUATING",  # critical new evidence supersedes target
            "RESEARCHING",  # request_research → new revision work
            "CANCELLED",
            "FAILED",
        }
    ),
    "INFORMATION_REQUESTED": frozenset(
        {
            "AWAITING_REVIEW",
            "RESEARCHING",  # new evidence / upgrade revision
            "CANCELLED",
            "FAILED",
            "REJECTED",
        }
    ),
    "DELIVERING": frozenset({"COMPLETED", "FAILED", "CANCELLED"}),
    "COMPLETED": frozenset(),
    "REJECTED": frozenset(),
    "BLOCKED_CONFIGURATION": frozenset(
        {
            "PLANNING",
            "RESEARCHING",
            "VALIDATING",
            "EVALUATING",
            "CRITIQUING",
            "CANCELLED",
            "FAILED",
        }
    ),
    "BUDGET_EXHAUSTED": frozenset(
        {
            "RESEARCHING",  # after audited budget override → new revision
            "CANCELLED",
            "FAILED",
            "REJECTED",
        }
    ),
    "CANCELLED": frozenset(),
    "FAILED": frozenset(),
}

TERMINAL: frozenset[AssessmentState] = frozenset(
    {"COMPLETED", "REJECTED", "CANCELLED", "FAILED"}
)


class LifecycleError(ValueError):
    """Raised when a transition is not allowed."""


def can_transition(current: AssessmentState, nxt: AssessmentState) -> bool:
    if current == nxt:
        return False
    return nxt in ALLOWED_TRANSITIONS.get(current, frozenset())


def assert_transition(current: AssessmentState, nxt: AssessmentState) -> None:
    if not can_transition(current, nxt):
        raise LifecycleError(f"illegal transition {current} → {nxt}")


def transition(current: AssessmentState, nxt: AssessmentState) -> AssessmentState:
    assert_transition(current, nxt)
    return nxt
