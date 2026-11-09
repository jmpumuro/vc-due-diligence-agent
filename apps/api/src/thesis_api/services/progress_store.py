"""Durable domain-progress events — reconstructable after refresh/worker restart."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from thesis_api.db.models_research import DomainProgressEventRow
from thesis_api.tenant import TenantContext

# Public progress payload allowlist — never leak prompts, private text, credentials.
_SAFE_DATA_KEYS = frozenset(
    {
        "status",
        "active_domains",
        "completed_domains",
        "research_tasks_done",
        "research_tasks_total",
        "retrieval_done",
        "retrieval_total",
        "claims_verified",
        "claims_total",
        "contradictions_open",
        "contradictions_detected",
        "evidence_sufficiency",
        "partial_results",
        "provider_failures",
        "human_review_status",
        "documents_indexed",
        "documents_pending",
        "error_code",
        "task_name",
        "count",
        "llm_used",
        "fetched",
        "independent_count",
        "snapshot_id",
        "deep_pass",
        "fetched_domain_count",
    }
)


def sanitize_progress_data(data: dict[str, Any] | None) -> dict[str, Any]:
    if not data:
        return {}
    out: dict[str, Any] = {}
    for k, v in data.items():
        if k not in _SAFE_DATA_KEYS:
            continue
        if isinstance(v, (str, int, float, bool)) or v is None:
            out[k] = v
        elif isinstance(v, list) and all(isinstance(i, (str, int, float, bool)) for i in v):
            out[k] = v
        elif isinstance(v, dict):
            # shallow safe nested maps of scalars only
            nested = {
                sk: sv
                for sk, sv in v.items()
                if isinstance(sk, str) and isinstance(sv, (str, int, float, bool, type(None)))
            }
            if nested:
                out[k] = nested
    return out


async def append_progress_event(
    session: AsyncSession,
    tenant: TenantContext,
    *,
    assessment_id: str,
    revision: int,
    event_type: str,
    message: str,
    domain_id: str | None = None,
    data: dict[str, Any] | None = None,
) -> DomainProgressEventRow:
    row = DomainProgressEventRow(
        firm_id=tenant.firm_id,
        assessment_id=assessment_id,
        revision=revision,
        event_type=event_type,
        domain_id=domain_id,
        message=message[:2000],
        data=sanitize_progress_data(data),
        occurred_at=datetime.now(timezone.utc),
    )
    session.add(row)
    await session.flush()
    return row


async def list_progress_events(
    session: AsyncSession,
    tenant: TenantContext,
    *,
    assessment_id: str,
    after_event_id: int = 0,
    limit: int = 100,
) -> list[DomainProgressEventRow]:
    limit = max(1, min(limit, 500))
    rows = (
        await session.execute(
            select(DomainProgressEventRow)
            .where(
                and_(
                    DomainProgressEventRow.firm_id == tenant.firm_id,
                    DomainProgressEventRow.assessment_id == assessment_id,
                    DomainProgressEventRow.event_id > after_event_id,
                )
            )
            .order_by(DomainProgressEventRow.event_id.asc())
            .limit(limit)
        )
    ).scalars().all()
    return list(rows)


def event_to_public_dict(row: DomainProgressEventRow) -> dict[str, Any]:
    return {
        "event_id": row.event_id,
        "assessment_id": row.assessment_id,
        "revision": row.revision,
        "event_type": row.event_type,
        "domain_id": row.domain_id,
        "message": row.message,
        "data": sanitize_progress_data(row.data or {}),
        "occurred_at": row.occurred_at.isoformat() if row.occurred_at else None,
    }


def reconstruct_progress_summary(events: list[DomainProgressEventRow]) -> dict[str, Any]:
    """Derive UI summary from durable event history (no invented percentages)."""
    active: set[str] = set()
    completed: set[str] = set()
    assessment_status = "unknown"
    contradictions_detected = 0
    claims_verified = 0
    claims_total = 0
    provider_failures = 0
    human_review = "none"
    sufficiency: dict[str, str] = {}
    partial = False

    for e in events:
        data = e.data or {}
        if e.event_type in ("assessment.status", "stage"):
            assessment_status = str(data.get("status") or e.message)
        if e.domain_id:
            if e.event_type == "domain.status":
                st = str(data.get("status") or "")
                if st == "completed":
                    completed.add(e.domain_id)
                    active.discard(e.domain_id)
                elif st in ("active", "running", "researching"):
                    active.add(e.domain_id)
                    completed.discard(e.domain_id)
        if "contradictions_detected" in data:
            contradictions_detected = max(
                contradictions_detected, int(data["contradictions_detected"])
            )
        if "claims_verified" in data:
            claims_verified = max(claims_verified, int(data["claims_verified"]))
        if "claims_total" in data:
            claims_total = max(claims_total, int(data["claims_total"]))
        if "provider_failures" in data:
            provider_failures = max(provider_failures, int(data["provider_failures"]))
        if "human_review_status" in data:
            human_review = str(data["human_review_status"])
        if "evidence_sufficiency" in data and e.domain_id:
            sufficiency[e.domain_id] = str(data["evidence_sufficiency"])
        if data.get("partial_results"):
            partial = True

    return {
        "assessment_status": assessment_status,
        "active_domains": sorted(active),
        "completed_domains": sorted(completed),
        "claims_verified": claims_verified,
        "claims_total": claims_total if claims_total else None,
        "contradictions_detected": contradictions_detected,
        "evidence_sufficiency": sufficiency,
        "partial_results": partial,
        "provider_failures": provider_failures,
        "human_review_status": human_review,
        "last_event_id": events[-1].event_id if events else 0,
    }
