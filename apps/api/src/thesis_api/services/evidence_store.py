# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Thesis contributors
"""Persist evidence snapshots and spans — Stage 4 provenance."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from thesis_api.db.models_research import EvidenceSnapshotRow, EvidenceSpanRow
from thesis_api.tenant import TenantContext


def sha256_hex(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


async def insert_snapshot(
    session: AsyncSession,
    tenant: TenantContext,
    *,
    canonical_url: str,
    body: bytes,
    content_type: str,
    http_status: int | None = None,
    classification: str = "public",
    snapshot_id: UUID | None = None,
    retrieved_at: datetime | None = None,
) -> EvidenceSnapshotRow:
    sid = str(snapshot_id or uuid4())
    existing = await session.get(EvidenceSnapshotRow, sid)
    if existing is not None:
        tenant.assert_firm(existing.firm_id)
        return existing
    row = EvidenceSnapshotRow(
        snapshot_id=sid,
        firm_id=tenant.firm_id,
        canonical_url=canonical_url,
        retrieved_at=retrieved_at or datetime.now(timezone.utc),
        content_type=(content_type or "application/octet-stream")[:128],
        normalized_sha256=sha256_hex(body),
        http_status=http_status,
        classification=classification,
    )
    session.add(row)
    await session.flush()
    return row


async def insert_span(
    session: AsyncSession,
    tenant: TenantContext,
    *,
    snapshot_id: str,
    text: str,
    start_offset: int = 0,
    end_offset: int | None = None,
    span_id: UUID | None = None,
) -> EvidenceSpanRow:
    sid = str(span_id or uuid4())
    existing = await session.get(EvidenceSpanRow, sid)
    if existing is not None:
        tenant.assert_firm(existing.firm_id)
        return existing
    passage = text or ""
    end = end_offset if end_offset is not None else start_offset + len(passage)
    row = EvidenceSpanRow(
        span_id=sid,
        firm_id=tenant.firm_id,
        snapshot_id=snapshot_id,
        start_offset=max(0, start_offset),
        end_offset=max(start_offset, end),
        text=passage[:8000],
        text_sha256=sha256_hex(passage),
    )
    session.add(row)
    await session.flush()
    return row


async def persist_fetch_evidence(
    session: AsyncSession,
    tenant: TenantContext,
    *,
    canonical_url: str,
    body: bytes,
    content_type: str,
    http_status: int | None,
    passage: str,
) -> tuple[EvidenceSnapshotRow, EvidenceSpanRow]:
    """Write snapshot + span and return both (immutable lineage inputs for claims)."""
    snap = await insert_snapshot(
        session,
        tenant,
        canonical_url=canonical_url,
        body=body,
        content_type=content_type,
        http_status=http_status,
    )
    # Locate passage in decoded text when possible
    try:
        decoded = body.decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        decoded = ""
    start = decoded.find(passage[:80]) if passage and decoded else 0
    if start < 0:
        start = 0
    span = await insert_span(
        session,
        tenant,
        snapshot_id=snap.snapshot_id,
        text=passage or decoded[:500] or canonical_url,
        start_offset=start,
    )
    return snap, span
