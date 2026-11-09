"""Durable SSE domain-progress stream."""

from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from thesis_api.db.models import AssessmentRow
from thesis_api.db.session import SessionLocal, get_session
from thesis_api.deps import get_tenant
from thesis_api.services.progress_store import (
    append_progress_event,
    event_to_public_dict,
    list_progress_events,
    reconstruct_progress_summary,
)
from thesis_api.tenant import TenantContext, TenantIsolationError

router = APIRouter(tags=["progress"])

HEARTBEAT_SECONDS = 15
POLL_SECONDS = 1.0


async def _assert_assessment(
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


@router.get("/assessments/{assessment_id}/progress")
async def get_progress_snapshot(
    assessment_id: str,
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(get_tenant),
) -> dict:
    await _assert_assessment(session, tenant, assessment_id)
    events = await list_progress_events(
        session, tenant, assessment_id=assessment_id, after_event_id=0, limit=500
    )
    return {
        "summary": reconstruct_progress_summary(events),
        "events": [event_to_public_dict(e) for e in events],
    }


@router.get("/assessments/{assessment_id}/progress/stream")
async def stream_progress(
    assessment_id: str,
    request: Request,
    last_event_id: int | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(get_tenant),
) -> StreamingResponse:
    await _assert_assessment(session, tenant, assessment_id)
    # Prefer Last-Event-ID header (SSE reconnect) over query
    header_id = request.headers.get("last-event-id")
    cursor = 0
    if header_id and header_id.isdigit():
        cursor = int(header_id)
    elif last_event_id is not None:
        cursor = last_event_id

    firm_id = tenant.firm_id
    user_id = tenant.user_id
    roles = tenant.roles
    is_demo = tenant.is_demo_session

    async def event_generator() -> AsyncIterator[str]:
        nonlocal cursor
        last_heartbeat = asyncio.get_event_loop().time()
        # Replay missed events first
        async with SessionLocal() as db:
            tenant_ctx = TenantContext(
                firm_id=firm_id, user_id=user_id, roles=roles, is_demo_session=is_demo
            )
            missed = await list_progress_events(
                db, tenant_ctx, assessment_id=assessment_id, after_event_id=cursor, limit=200
            )
            for row in missed:
                payload = event_to_public_dict(row)
                cursor = row.event_id
                yield f"id: {row.event_id}\nevent: progress\ndata: {json.dumps(payload)}\n\n"

        while True:
            if await request.is_disconnected():
                break
            now = asyncio.get_event_loop().time()
            async with SessionLocal() as db:
                tenant_ctx = TenantContext(
                    firm_id=firm_id, user_id=user_id, roles=roles, is_demo_session=is_demo
                )
                # Re-check tenant isolation each poll
                row = (
                    await db.execute(
                        select(AssessmentRow).where(AssessmentRow.id == assessment_id)
                    )
                ).scalar_one_or_none()
                if row is None or row.firm_id != firm_id:
                    yield 'event: error\ndata: {"code":"FORBIDDEN"}\n\n'
                    break
                fresh = await list_progress_events(
                    db, tenant_ctx, assessment_id=assessment_id, after_event_id=cursor, limit=50
                )
                for ev in fresh:
                    payload = event_to_public_dict(ev)
                    cursor = ev.event_id
                    yield f"id: {ev.event_id}\nevent: progress\ndata: {json.dumps(payload)}\n\n"
                    last_heartbeat = now

            if now - last_heartbeat >= HEARTBEAT_SECONDS:
                yield ": heartbeat\n\n"
                last_heartbeat = now
            await asyncio.sleep(POLL_SECONDS)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/assessments/{assessment_id}/progress/events", status_code=201)
async def append_progress(
    assessment_id: str,
    body: dict,
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(get_tenant),
) -> dict:
    """Authorized append for workers/tests — sanitized public fields only."""
    assessment = await _assert_assessment(session, tenant, assessment_id)
    event_type = str(body.get("event_type") or "stage")
    message = str(body.get("message") or "")
    domain_id = body.get("domain_id")
    data = body.get("data") if isinstance(body.get("data"), dict) else {}
    revision = int(body.get("revision") or assessment.revision)
    row = await append_progress_event(
        session,
        tenant,
        assessment_id=assessment_id,
        revision=revision,
        event_type=event_type,
        message=message,
        domain_id=str(domain_id) if domain_id else None,
        data=data,
    )
    await session.commit()
    return event_to_public_dict(row)