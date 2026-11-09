"""Human review + watchlist + outbox ops + deal team (Stages 6–7)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from thesis_api.db.models import AssessmentRow
from thesis_api.db.models_stage6 import DealTeamMemberRow, NotificationRow, WatchlistEntryRow
from thesis_api.db.session import get_session
from thesis_api.deps import get_tenant
from thesis_api.services.outbox import dispatch_pending_local, list_pending
from thesis_api.services.review_store import ReviewAlreadyDecided, StaleReviewTarget, submit_review
from thesis_api.tenant import TenantContext, TenantIsolationError
from thesis_contracts.review import SubmitReviewRequest

router = APIRouter(tags=["review"])


async def _assessment(
    session: AsyncSession, tenant: TenantContext, assessment_id: str
) -> AssessmentRow:
    row = (
        await session.execute(select(AssessmentRow).where(AssessmentRow.id == assessment_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    try:
        tenant.assert_firm(row.firm_id)
    except TenantIsolationError as exc:
        raise HTTPException(status_code=404, detail="NOT_FOUND") from exc
    return row


@router.post("/assessments/{assessment_id}/review")
async def post_review(
    assessment_id: str,
    body: SubmitReviewRequest,
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(get_tenant),
) -> dict:
    row = await _assessment(session, tenant, assessment_id)
    try:
        decision = await submit_review(session, tenant, assessment=row, request=body)
        workflow_id = None
        if body.decision == "request_research":
            from thesis_api.routes.screening import _start_workflow

            prior = row.workflow_id
            try:
                workflow_id = await _start_workflow(
                    firm_id=tenant.firm_id,
                    user_id=tenant.user_id,
                    assessment_id=row.id,
                    company_name=row.company_name,
                    level=int(row.level or 1),
                    revision=int(row.revision or 1),
                    prior_workflow_id=prior,
                )
                row.workflow_id = workflow_id
            except Exception as exc:  # noqa: BLE001
                await session.commit()
                raise HTTPException(
                    status_code=503,
                    detail=f"RESEARCH_WORKFLOW_UNAVAILABLE: {exc}",
                ) from exc
        await session.commit()
    except StaleReviewTarget as exc:
        raise HTTPException(status_code=409, detail="STALE_REVIEW_TARGET") from exc
    except ReviewAlreadyDecided as exc:
        raise HTTPException(status_code=409, detail="REVIEW_ALREADY_DECIDED") from exc
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "ok": True,
        "decision_id": decision.id,
        "decision": decision.decision,
        "assessment_state": row.state,
        "revision": row.revision,
        "workflow_id": row.workflow_id,
    }


class DealTeamAdd(BaseModel):
    user_id: str
    role: str = "member"


@router.get("/assessments/{assessment_id}/deal-team")
async def get_deal_team(
    assessment_id: str,
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(get_tenant),
) -> dict:
    await _assessment(session, tenant, assessment_id)
    rows = (
        await session.execute(
            select(DealTeamMemberRow).where(
                DealTeamMemberRow.firm_id == tenant.firm_id,
                DealTeamMemberRow.assessment_id == assessment_id,
            )
        )
    ).scalars().all()
    return {
        "items": [
            {"id": r.id, "user_id": r.user_id, "role": r.role, "assessment_id": r.assessment_id}
            for r in rows
        ]
    }


@router.post("/assessments/{assessment_id}/deal-team", status_code=201)
async def add_deal_team(
    assessment_id: str,
    body: DealTeamAdd,
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(get_tenant),
) -> dict:
    if "partner" not in tenant.roles and "admin" not in tenant.roles and "owner" not in tenant.roles:
        raise HTTPException(status_code=403, detail="FORBIDDEN")
    await _assessment(session, tenant, assessment_id)
    existing = (
        await session.execute(
            select(DealTeamMemberRow).where(
                DealTeamMemberRow.assessment_id == assessment_id,
                DealTeamMemberRow.user_id == body.user_id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return {"id": existing.id, "user_id": existing.user_id, "role": existing.role}
    row = DealTeamMemberRow(
        id=str(uuid4()),
        firm_id=tenant.firm_id,
        assessment_id=assessment_id,
        user_id=body.user_id,
        role=body.role,
    )
    session.add(row)
    await session.commit()
    return {"id": row.id, "user_id": row.user_id, "role": row.role}


class WatchlistCreate(BaseModel):
    company_name: str = Field(min_length=1, max_length=255)
    primary_domain: str | None = None
    cadence: str = "weekly"
    rules: dict = Field(default_factory=dict)


class WatchlistPatch(BaseModel):
    paused: bool | None = None
    cadence: str | None = None
    rules: dict | None = None


@router.get("/watchlist")
async def get_watchlist(
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(get_tenant),
) -> dict:
    rows = (
        await session.execute(
            select(WatchlistEntryRow)
            .where(WatchlistEntryRow.firm_id == tenant.firm_id)
            .order_by(WatchlistEntryRow.created_at.desc())
        )
    ).scalars().all()
    return {
        "items": [
            {
                "id": r.id,
                "company_name": r.company_name,
                "primary_domain": r.primary_domain,
                "cadence": r.cadence,
                "paused": r.paused,
                "rules": r.rules,
            }
            for r in rows
        ]
    }


@router.post("/watchlist", status_code=201)
async def create_watchlist(
    body: WatchlistCreate,
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(get_tenant),
) -> dict:
    row = WatchlistEntryRow(
        id=str(uuid4()),
        firm_id=tenant.firm_id,
        company_name=body.company_name,
        primary_domain=body.primary_domain,
        cadence=body.cadence,
        rules=body.rules,
        paused=False,
        created_by=tenant.user_id,
    )
    session.add(row)
    await session.commit()
    return {"id": row.id, "company_name": row.company_name}


@router.patch("/watchlist/{entry_id}")
async def patch_watchlist(
    entry_id: str,
    body: WatchlistPatch,
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(get_tenant),
) -> dict:
    row = await session.get(WatchlistEntryRow, entry_id)
    if row is None or row.firm_id != tenant.firm_id:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    if body.paused is not None:
        row.paused = body.paused
    if body.cadence is not None:
        row.cadence = body.cadence
    if body.rules is not None:
        row.rules = body.rules
    await session.commit()
    return {"id": row.id, "paused": row.paused, "cadence": row.cadence}


@router.post("/watchlist/{entry_id}/reassess")
async def reassess_watchlist(
    entry_id: str,
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(get_tenant),
) -> dict:
    """Queue a watchlist reassessment via transactional outbox (Stage 7)."""
    from thesis_api.services.outbox import enqueue_outbox

    row = await session.get(WatchlistEntryRow, entry_id)
    if row is None or row.firm_id != tenant.firm_id:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    if row.paused:
        raise HTTPException(status_code=409, detail="WATCHLIST_PAUSED")
    event = await enqueue_outbox(
        session,
        firm_id=tenant.firm_id,
        subject_type="watchlist",
        subject_id=row.id,
        event_type="watchlist.reassess",
        idempotency_key=f"watchlist.reassess:{row.id}:{uuid4()}",
        payload={
            "watchlist_id": row.id,
            "company_name": row.company_name,
            "cadence": row.cadence,
        },
    )
    await session.commit()
    return {
        "ok": True,
        "outbox_id": event.outbox_id,
        "event_type": event.event_type,
        "company_name": row.company_name,
    }


@router.get("/notifications")
async def list_notifications(
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(get_tenant),
    limit: int = 50,
) -> dict:
    from thesis_api.services.outbox import notification_copy

    rows = (
        await session.execute(
            select(NotificationRow)
            .where(NotificationRow.firm_id == tenant.firm_id)
            .order_by(NotificationRow.created_at.desc())
            .limit(max(1, min(limit, 200)))
        )
    ).scalars().all()

    subject_ids = {r.subject_id for r in rows if r.subject_type == "assessment" and r.subject_id}
    names: dict[str, str] = {}
    if subject_ids:
        assessments = (
            await session.execute(
                select(AssessmentRow).where(
                    AssessmentRow.firm_id == tenant.firm_id,
                    AssessmentRow.id.in_(subject_ids),
                )
            )
        ).scalars().all()
        names = {a.id: a.company_name for a in assessments}

    items = []
    for r in rows:
        payload = dict(r.payload or {})
        company = str(payload.get("company_name") or names.get(r.subject_id) or "").strip()
        if company and "company_name" not in payload:
            payload["company_name"] = company
        # Re-render partner copy for older rows that stored raw titles.
        title, body = notification_copy(r.event_type, payload)
        items.append(
            {
                "id": r.id,
                "event_type": r.event_type,
                "title": title or r.title,
                "body": body if body is not None else r.body,
                "company_name": company or None,
                "subject_id": r.subject_id,
                "read_at": r.read_at.isoformat() if r.read_at else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
        )
    return {"items": items}


class MarkNotificationsReadBody(BaseModel):
    ids: list[str] | None = None


@router.post("/notifications/mark-read")
async def mark_notifications_read(
    body: MarkNotificationsReadBody,
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(get_tenant),
) -> dict:
    """Mark specific notifications read, or all unread for the firm when ids omitted."""
    now = datetime.now(timezone.utc)
    q = select(NotificationRow).where(
        NotificationRow.firm_id == tenant.firm_id,
        NotificationRow.read_at.is_(None),
    )
    if body.ids:
        q = q.where(NotificationRow.id.in_(body.ids))
    rows = (await session.execute(q)).scalars().all()
    for row in rows:
        row.read_at = now
    await session.commit()
    return {"ok": True, "marked": len(rows)}


@router.get("/ops/outbox/summary")
async def outbox_summary(
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(get_tenant),
) -> dict:
    pending = await list_pending(session, firm_id=tenant.firm_id, limit=100)
    return {
        "pending": len(pending),
        "items": [
            {
                "outbox_id": p.outbox_id,
                "event_type": p.event_type,
                "subject_id": p.subject_id,
                "sequence": p.sequence,
            }
            for p in pending[:20]
        ],
    }


@router.post("/ops/outbox/dispatch")
async def outbox_dispatch(
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(get_tenant),
    via_workflow: bool = False,
) -> dict:
    if "admin" not in tenant.roles and "owner" not in tenant.roles and "partner" not in tenant.roles:
        raise HTTPException(status_code=403, detail="FORBIDDEN")
    if via_workflow:
        from temporalio.client import Client

        from thesis_api.settings import settings
        from thesis_api.temporal_app.workflows import OutboxDispatchWorkflow

        client = await Client.connect(settings.temporal_host)
        handle = await client.start_workflow(
            OutboxDispatchWorkflow.run,
            {"firm_id": tenant.firm_id},
            id=f"outbox-dispatch:{tenant.firm_id}:{uuid4()}",
            task_queue="q.system",
        )
        return {"ok": True, "workflow_id": handle.id, "via_workflow": True}
    result = await dispatch_pending_local(session, firm_id=tenant.firm_id)
    await session.commit()
    return result
