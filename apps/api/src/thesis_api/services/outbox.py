# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Thesis contributors
"""Transactional outbox — delivery effects commit with business changes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from thesis_api.db.models_stage6 import NotificationRow, OutboxEventRow
from thesis_api.settings import settings

_FORBIDDEN_PAYLOAD_KEYS = frozenset({"text", "body", "prompt", "content", "raw", "document_text"})


def sanitize_outbox_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Reject private-document text keys from outbox / notification payloads."""
    safe: dict[str, Any] = {}
    for k, v in (payload or {}).items():
        if k.lower() in _FORBIDDEN_PAYLOAD_KEYS:
            continue
        safe[k] = v
    return safe


def notification_copy(event_type: str, payload: dict[str, Any]) -> tuple[str, str | None]:
    """Partner-facing title/body — avoid raw event types and vendor jargon."""
    company = str(payload.get("company_name") or "").strip()
    state = str(payload.get("state") or "").strip()
    rec = str(payload.get("recommendation") or "").strip()
    decision = str(payload.get("decision") or "").strip()

    if event_type == "review.requested":
        title = f"{company}: ready for partner decision" if company else "Ready for partner decision"
        return title, "Open the report and decide on this revision."
    if event_type == "review.decided":
        title = f"{company}: decision recorded" if company else "Decision recorded"
        return title, f"Partner call: {decision}" if decision else None
    if event_type == "assessment.memo_ready":
        title = f"{company}: memo ready" if company else "Memo ready"
        return title, f"Agent suggestion: {rec}" if rec else "Draft memo is ready for review."
    if event_type == "watchlist.reassess":
        title = f"{company}: Watchlist reassess queued" if company else "Watchlist reassess queued"
        return title, None
    if event_type == "assessment.state_changed":
        # Only partner-meaningful states get a dedicated title; others stay terse.
        state_titles = {
            "AWAITING_REVIEW": "Ready for partner decision",
            "COMPLETED": "Assessment completed",
            "REJECTED": "Assessment passed / closed",
            "FAILED": "Research failed",
            "INFORMATION_REQUESTED": "Waiting on company materials",
            "BLOCKED_CONFIGURATION": "Paused — setup needed",
        }
        label = state_titles.get(state, "Screening update")
        title = f"{company}: {label}" if company else label
        return title, state or None

    title = event_type.replace(".", " ").replace("_", " ").strip().capitalize()
    if company:
        title = f"{company}: {title}"
    return title, None


async def enqueue_outbox(
    session: AsyncSession,
    *,
    firm_id: str,
    subject_type: str,
    subject_id: str,
    event_type: str,
    idempotency_key: str,
    payload: dict[str, Any] | None = None,
) -> OutboxEventRow:
    existing = (
        await session.execute(
            select(OutboxEventRow).where(
                OutboxEventRow.firm_id == firm_id,
                OutboxEventRow.idempotency_key == idempotency_key,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    safe_payload = sanitize_outbox_payload(payload)

    seq = (
        await session.execute(
            select(func.coalesce(func.max(OutboxEventRow.sequence), 0)).where(
                OutboxEventRow.firm_id == firm_id,
                OutboxEventRow.subject_id == subject_id,
            )
        )
    ).scalar_one()

    row = OutboxEventRow(
        outbox_id=str(uuid4()),
        firm_id=firm_id,
        subject_type=subject_type,
        subject_id=subject_id,
        event_type=event_type,
        payload=safe_payload,
        idempotency_key=idempotency_key,
        sequence=int(seq) + 1,
        status="pending",
        attempts=0,
    )
    session.add(row)
    await session.flush()
    return row


async def list_pending(
    session: AsyncSession, *, firm_id: str | None = None, limit: int = 50
) -> list[OutboxEventRow]:
    q = select(OutboxEventRow).where(OutboxEventRow.status == "pending")
    if firm_id:
        q = q.where(OutboxEventRow.firm_id == firm_id)
    q = q.order_by(OutboxEventRow.created_at.asc()).limit(max(1, min(limit, 200)))
    return list((await session.execute(q)).scalars().all())


async def mark_delivered(session: AsyncSession, outbox_id: str) -> OutboxEventRow:
    row = await session.get(OutboxEventRow, outbox_id)
    if row is None:
        raise KeyError(outbox_id)
    if row.status == "delivered":
        return row
    row.status = "delivered"
    row.delivered_at = datetime.now(timezone.utc)
    await session.flush()
    return row


async def mark_failed(session: AsyncSession, outbox_id: str, error: str) -> OutboxEventRow:
    row = await session.get(OutboxEventRow, outbox_id)
    if row is None:
        raise KeyError(outbox_id)
    row.attempts = int(row.attempts) + 1
    row.last_error = error[:2000]
    if row.attempts >= 5:
        row.status = "failed"
    await session.flush()
    return row


async def _deliver_to_notification(session: AsyncSession, row: OutboxEventRow) -> NotificationRow:
    existing = (
        await session.execute(
            select(NotificationRow).where(
                NotificationRow.firm_id == row.firm_id,
                NotificationRow.outbox_id == row.outbox_id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    title, body = notification_copy(row.event_type, row.payload or {})
    note = NotificationRow(
        id=str(uuid4()),
        firm_id=row.firm_id,
        user_id=None,
        outbox_id=row.outbox_id,
        event_type=row.event_type,
        subject_type=row.subject_type,
        subject_id=row.subject_id,
        title=title,
        body=body,
        payload=sanitize_outbox_payload(row.payload),
    )
    session.add(note)
    await session.flush()
    return note


async def _deliver_webhook(row: OutboxEventRow) -> dict[str, Any]:
    url = settings.outbox_webhook_url.strip()
    if not url:
        return {"skipped": True, "reason": "no_webhook"}
    payload = {
        "outbox_id": row.outbox_id,
        "firm_id": row.firm_id,
        "event_type": row.event_type,
        "subject_type": row.subject_type,
        "subject_id": row.subject_id,
        "payload": sanitize_outbox_payload(row.payload),
        "sequence": row.sequence,
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.post(url, json=payload)
        res.raise_for_status()
    return {"skipped": False, "status_code": res.status_code}


async def dispatch_pending_local(
    session: AsyncSession, *, firm_id: str | None = None
) -> dict[str, int]:
    """Deliver pending outbox rows → notifications (+ optional webhook). Idempotent."""
    pending = await list_pending(session, firm_id=firm_id)
    delivered = 0
    failed = 0
    webhooks = 0
    for row in pending:
        try:
            await _deliver_to_notification(session, row)
            hook = await _deliver_webhook(row)
            if not hook.get("skipped"):
                webhooks += 1
            await mark_delivered(session, row.outbox_id)
            delivered += 1
        except Exception as exc:  # noqa: BLE001
            await mark_failed(session, row.outbox_id, str(exc))
            failed += 1
    return {"delivered": delivered, "failed": failed, "webhooks": webhooks}
