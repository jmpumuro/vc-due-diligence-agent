"""Tool permissions and review digest contracts."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from thesis_contracts.review import ReviewTarget, SubmitReviewRequest, target_digest
from thesis_contracts.tools import tool_allowed


def test_planner_has_no_network_tools() -> None:
    assert not tool_allowed("planner", "web_search")
    assert not tool_allowed("verification", "web_search")
    assert tool_allowed("research", "web_search")
    assert tool_allowed("verification", "sanctions_check")


def test_review_digest_stable() -> None:
    target = ReviewTarget(
        assessment_id=uuid4(),
        assessment_revision=1,
        evidence_snapshot_id=uuid4(),
        evaluation_id=uuid4(),
        memo_version_id=uuid4(),
        review_policy_version="single-reviewer@1",
    )
    assert target_digest(target) == target_digest(target)
    assert len(target_digest(target)) == 64


def test_request_information_requires_items() -> None:
    target = ReviewTarget(
        assessment_id=uuid4(),
        assessment_revision=1,
        evidence_snapshot_id=uuid4(),
        evaluation_id=uuid4(),
        memo_version_id=uuid4(),
        review_policy_version="single-reviewer@1",
    )
    with pytest.raises(ValidationError):
        SubmitReviewRequest(
            target=target,
            decision="request_information",
            requested_items=[],
            idempotency_key="k1",
        )
