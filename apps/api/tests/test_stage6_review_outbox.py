"""Stage 6–7: review digest, stale target, outbox sanitize, domains."""

from __future__ import annotations

from uuid import uuid4

from thesis_api.services.domains import ALL_DOMAINS, domains_for_level
from thesis_api.services.outbox import enqueue_outbox, notification_copy, sanitize_outbox_payload
from thesis_api.services.screening import recommend_from_gates
from thesis_contracts.review import ReviewTarget, SubmitReviewRequest, target_digest


def test_twelve_domains_and_level1_subset() -> None:
    assert len(ALL_DOMAINS) == 12
    l1 = domains_for_level(1)
    assert "company" in l1 and "financials" not in l1
    assert "financials" in domains_for_level(3)


def test_review_target_digest_stable() -> None:
    t = ReviewTarget(
        assessment_id=uuid4(),
        assessment_revision=1,
        evidence_snapshot_id=uuid4(),
        evaluation_id=uuid4(),
        memo_version_id=uuid4(),
        review_policy_version="review-policy@1",
    )
    assert target_digest(t) == target_digest(t)
    t2 = t.model_copy(update={"assessment_revision": 2})
    assert target_digest(t) != target_digest(t2)


def test_submit_review_request_requires_items_for_info() -> None:
    t = ReviewTarget(
        assessment_id=uuid4(),
        assessment_revision=1,
        evidence_snapshot_id=uuid4(),
        evaluation_id=uuid4(),
        memo_version_id=uuid4(),
        review_policy_version="review-policy@1",
    )
    try:
        SubmitReviewRequest(
            target=t,
            decision="request_information",
            requested_items=[],
            idempotency_key="k1",
        )
    except Exception:
        return
    assert False, "expected validation error"


def test_recommend_from_gates() -> None:
    assert recommend_from_gates({"company": "sufficient", "team": "sufficient"}, level=1) == "advance"
    assert recommend_from_gates({"company": "insufficient"}, level=1) == "inconclusive"
    assert recommend_from_gates({"company": "partial", "team": "sufficient"}, level=1) == "hold"
    assert recommend_from_gates({"company": "partial", "team": "partial"}, level=1) == "inconclusive"
    assert recommend_from_gates(
        {"company": "insufficient", "team": "insufficient"}, level=2
    ) == "pass"


def test_outbox_enqueue_importable() -> None:
    assert callable(enqueue_outbox)


def test_outbox_sanitize_strips_private_keys() -> None:
    safe = sanitize_outbox_payload(
        {
            "assessment_id": "a1",
            "text": "PRIVATE DOC",
            "content": "secret",
            "decision": "approve",
        }
    )
    assert "text" not in safe and "content" not in safe
    assert safe["decision"] == "approve"
    assert safe["assessment_id"] == "a1"


def test_notification_copy() -> None:
    title, body = notification_copy("review.decided", {"decision": "approve"})
    assert title == "Decision recorded"
    assert body and "approve" in body
