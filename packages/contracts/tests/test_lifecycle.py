"""Lifecycle and ledger transition contract tests."""

from __future__ import annotations

import pytest

from thesis_contracts.budget import can_transition_budget
from thesis_contracts.ledger import can_transition_ledger, transition_ledger, LedgerTransitionError
from thesis_contracts.lifecycle import (
    ALLOWED_TRANSITIONS,
    AssessmentState,
    LifecycleError,
    TERMINAL,
    assert_transition,
    can_transition,
    transition,
)


def test_happy_path_spine() -> None:
    path: list[AssessmentState] = [
        "CREATED",
        "PLANNING",
        "RESEARCHING",
        "VALIDATING",
        "EVALUATING",
        "CRITIQUING",
        "MEMO_READY",
        "AWAITING_REVIEW",
        "DELIVERING",
        "COMPLETED",
    ]
    state = path[0]
    for nxt in path[1:]:
        state = transition(state, nxt)
    assert state == "COMPLETED"


def test_information_request_branch() -> None:
    assert can_transition("AWAITING_REVIEW", "INFORMATION_REQUESTED")
    assert can_transition("INFORMATION_REQUESTED", "AWAITING_REVIEW")


def test_terminal_states_have_no_exits() -> None:
    for state in TERMINAL:
        assert ALLOWED_TRANSITIONS[state] == frozenset()


def test_illegal_transition_raises() -> None:
    with pytest.raises(LifecycleError):
        assert_transition("CREATED", "COMPLETED")


def test_ledger_happy_path() -> None:
    assert transition_ledger("RESERVED", "IN_FLIGHT") == "IN_FLIGHT"
    assert transition_ledger("IN_FLIGHT", "SUCCEEDED") == "SUCCEEDED"


def test_ledger_unknown_to_reconciled() -> None:
    assert can_transition_ledger("UNKNOWN", "RECONCILED")
    with pytest.raises(LedgerTransitionError):
        transition_ledger("SUCCEEDED", "FAILED")


def test_budget_settle() -> None:
    assert can_transition_budget("held", "settled")
    assert not can_transition_budget("settled", "held")
