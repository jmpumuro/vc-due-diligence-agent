"""Heal assessment rows stuck after Temporal interrupt / orphan request_research."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from temporalio.client import Client
from temporalio.service import RPCError

from sqlalchemy import select

from thesis_api.db.models import AssessmentRow
from thesis_api.db.models_stage6 import ReviewTargetRow
from thesis_api.settings import settings
from thesis_contracts.lifecycle import can_transition, transition

logger = logging.getLogger("thesis_workflow_reconcile")

IN_FLIGHT = frozenset(
    {
        "CREATED",
        "PLANNING",
        "RESEARCHING",
        "VALIDATING",
        "EVALUATING",
        "CRITIQUING",
        "MEMO_READY",
    }
)

_SPINE = (
    "CREATED",
    "PLANNING",
    "RESEARCHING",
    "VALIDATING",
    "EVALUATING",
    "CRITIQUING",
    "MEMO_READY",
    "AWAITING_REVIEW",
)


def spine_rank(state: str) -> int | None:
    try:
        return _SPINE.index(state)
    except ValueError:
        return None


async def describe_workflow(workflow_id: str | None) -> dict[str, Any]:
    if not workflow_id:
        return {"status": "MISSING"}
    try:
        client = await Client.connect(settings.temporal_host)
        handle = client.get_workflow_handle(workflow_id)
        desc = await handle.describe()
        status = str(getattr(desc.status, "name", None) or desc.status)
        return {"status": status, "workflow_id": workflow_id}
    except RPCError as exc:
        logger.info("workflow describe failed for %s: %s", workflow_id, exc)
        return {"status": "MISSING", "workflow_id": workflow_id, "error": str(exc)}
    except Exception as exc:  # noqa: BLE001
        logger.warning("workflow describe error for %s: %s", workflow_id, exc)
        return {"status": "UNKNOWN", "workflow_id": workflow_id, "error": str(exc)}


async def terminate_workflow(workflow_id: str | None, *, reason: str) -> bool:
    if not workflow_id:
        return False
    try:
        client = await Client.connect(settings.temporal_host)
        handle = client.get_workflow_handle(workflow_id)
        desc = await handle.describe()
        status = str(getattr(desc.status, "name", None) or desc.status)
        if status == "RUNNING":
            await handle.terminate(reason)
            return True
    except Exception as exc:  # noqa: BLE001
        logger.info("terminate %s skipped: %s", workflow_id, exc)
    return False


async def _reopen_latest_review_target(session: AsyncSession, row: AssessmentRow) -> None:
    """Ensure partners can decide again after orphan RESEARCHING heal."""
    target = (
        await session.execute(
            select(ReviewTargetRow)
            .where(
                ReviewTargetRow.firm_id == row.firm_id,
                ReviewTargetRow.assessment_id == row.id,
            )
            .order_by(ReviewTargetRow.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if target is None:
        return
    target.status = "open"
    row.review_target_digest = target.target_digest


async def reconcile_assessment(session: AsyncSession, row: AssessmentRow) -> dict[str, Any]:
    """If DB says in-flight but Temporal is done/missing, heal the row.

    Lifecycle may be bypassed only for orphan RESEARCHING with an existing memo
    (request_research that never started a new run).
    """
    _ = session  # session held by caller for commit
    before = row.state
    if row.state not in IN_FLIGHT:
        return {"assessment_id": row.id, "changed": False, "state": row.state}

    info = await describe_workflow(row.workflow_id)
    status = info.get("status") or "UNKNOWN"

    if status == "RUNNING":
        return {"assessment_id": row.id, "changed": False, "state": row.state, "workflow": status}

    summary = dict(row.summary_json or {})
    has_review_target = isinstance(summary.get("review_target"), dict)

    # Orphan: memo/review payload exists, Temporal done, DB still researching
    # (typically request_research that never started a new run).
    if (
        row.state == "RESEARCHING"
        and has_review_target
        and status in {"COMPLETED", "FAILED", "CANCELED", "TERMINATED", "TIMED_OUT", "MISSING"}
    ):
        row.state = "AWAITING_REVIEW"
        await _reopen_latest_review_target(session, row)
        return {
            "assessment_id": row.id,
            "changed": True,
            "state": row.state,
            "workflow": status,
            "action": "restored_awaiting_review",
            "before": before,
        }

    # Happy path: still climbing toward review when Temporal already completed.
    if status == "COMPLETED" and has_review_target and row.state == "MEMO_READY":
        if can_transition(row.state, "AWAITING_REVIEW"):  # type: ignore[arg-type]
            row.state = transition(row.state, "AWAITING_REVIEW")  # type: ignore[arg-type]
            return {
                "assessment_id": row.id,
                "changed": True,
                "state": row.state,
                "workflow": status,
                "action": "opened_review",
                "before": before,
            }

    # Dead Temporal run while DB still mid-spine → FAILED so Restart works.
    if status in {"FAILED", "CANCELED", "TERMINATED", "TIMED_OUT", "MISSING"}:
        if can_transition(row.state, "FAILED"):  # type: ignore[arg-type]
            row.state = transition(row.state, "FAILED")  # type: ignore[arg-type]
            return {
                "assessment_id": row.id,
                "changed": True,
                "state": row.state,
                "workflow": status,
                "action": "marked_failed",
                "before": before,
            }

    return {
        "assessment_id": row.id,
        "changed": False,
        "state": row.state,
        "workflow": status,
    }
