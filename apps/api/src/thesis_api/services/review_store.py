"""Version-bound human review — STALE_REVIEW_TARGET / REVIEW_ALREADY_DECIDED."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from thesis_api.db.models import AssessmentRow
from thesis_api.db.models_stage6 import ReviewDecisionRow, ReviewTargetRow
from thesis_api.services.outbox import enqueue_outbox
from thesis_api.tenant import TenantContext
from thesis_contracts.lifecycle import transition
from thesis_contracts.review import ReviewTarget, SubmitReviewRequest, target_digest


class StaleReviewTarget(ValueError):
    pass


class ReviewAlreadyDecided(ValueError):
    pass


async def open_review_target(
    session: AsyncSession,
    tenant: TenantContext,
    *,
    assessment: AssessmentRow,
    target: ReviewTarget,
) -> ReviewTargetRow:
    tenant.assert_firm(assessment.firm_id)
    digest = target_digest(target)
    row = ReviewTargetRow(
        id=str(uuid4()),
        firm_id=tenant.firm_id,
        assessment_id=str(target.assessment_id),
        assessment_revision=target.assessment_revision,
        evidence_snapshot_id=str(target.evidence_snapshot_id),
        evaluation_id=str(target.evaluation_id),
        memo_version_id=str(target.memo_version_id),
        review_policy_version=target.review_policy_version,
        target_digest=digest,
        status="open",
    )
    session.add(row)
    assessment.review_target_digest = digest
    assessment.state = transition(assessment.state, "AWAITING_REVIEW")  # type: ignore[arg-type]
    await enqueue_outbox(
        session,
        firm_id=tenant.firm_id,
        subject_type="assessment",
        subject_id=str(assessment.id),
        event_type="review.requested",
        idempotency_key=f"review.requested:{digest}",
        payload={
            "assessment_id": str(assessment.id),
            "target_digest": digest,
            "company_name": assessment.company_name,
        },
    )
    await session.flush()
    return row


async def submit_review(
    session: AsyncSession,
    tenant: TenantContext,
    *,
    assessment: AssessmentRow,
    request: SubmitReviewRequest,
) -> ReviewDecisionRow:
    tenant.assert_firm(assessment.firm_id)

    # Idempotent replay
    existing = (
        await session.execute(
            select(ReviewDecisionRow).where(
                ReviewDecisionRow.firm_id == tenant.firm_id,
                ReviewDecisionRow.idempotency_key == request.idempotency_key,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    digest = target_digest(request.target)
    if assessment.review_target_digest and assessment.review_target_digest != digest:
        raise StaleReviewTarget("STALE_REVIEW_TARGET")
    if str(request.target.assessment_id) != assessment.id:
        raise StaleReviewTarget("STALE_REVIEW_TARGET")
    if request.target.assessment_revision != assessment.revision:
        raise StaleReviewTarget("STALE_REVIEW_TARGET")

    open_target = (
        await session.execute(
            select(ReviewTargetRow)
            .where(
                ReviewTargetRow.firm_id == tenant.firm_id,
                ReviewTargetRow.assessment_id == assessment.id,
                ReviewTargetRow.target_digest == digest,
                ReviewTargetRow.status == "open",
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if open_target is None:
        decided = (
            await session.execute(
                select(ReviewTargetRow).where(
                    ReviewTargetRow.firm_id == tenant.firm_id,
                    ReviewTargetRow.assessment_id == assessment.id,
                    ReviewTargetRow.target_digest == digest,
                    ReviewTargetRow.status == "decided",
                )
            )
        ).scalar_one_or_none()
        if decided is not None:
            raise ReviewAlreadyDecided("REVIEW_ALREADY_DECIDED")
        raise StaleReviewTarget("STALE_REVIEW_TARGET")

    decision = ReviewDecisionRow(
        id=str(uuid4()),
        firm_id=tenant.firm_id,
        assessment_id=assessment.id,
        target_digest=digest,
        decision=request.decision,
        comment=request.comment,
        requested_items=list(request.requested_items),
        actor_user_id=tenant.user_id,
        idempotency_key=request.idempotency_key,
    )
    session.add(decision)
    open_target.status = "decided"

    if request.decision == "approve":
        assessment.state = transition(assessment.state, "DELIVERING")  # type: ignore[arg-type]
        assessment.state = transition(assessment.state, "COMPLETED")  # type: ignore[arg-type]
    elif request.decision == "reject":
        assessment.state = transition(assessment.state, "REJECTED")  # type: ignore[arg-type]
    elif request.decision == "request_information":
        assessment.state = transition(assessment.state, "INFORMATION_REQUESTED")  # type: ignore[arg-type]
    else:  # request_research — bump revision; caller must start a new screening workflow
        assessment.revision = int(assessment.revision or 1) + 1
        assessment.state = transition(assessment.state, "RESEARCHING")  # type: ignore[arg-type]
        assessment.review_target_digest = None

    await enqueue_outbox(
        session,
        firm_id=tenant.firm_id,
        subject_type="assessment",
        subject_id=assessment.id,
        event_type="review.decided",
        idempotency_key=f"review.decided:{request.idempotency_key}",
        payload={
            "assessment_id": assessment.id,
            "decision": request.decision,
            "target_digest": digest,
            "company_name": assessment.company_name,
        },
    )
    await session.flush()
    return decision
