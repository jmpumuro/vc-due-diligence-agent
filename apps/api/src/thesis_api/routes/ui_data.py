"""UI-backing read APIs for Research app and Agent console."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from thesis_api.db.models import AssessmentRow
from thesis_api.db.models_research import DomainProgressEventRow
from thesis_api.db.models_stage6 import OutboxEventRow, ReviewTargetRow, WatchlistEntryRow
from thesis_api.db.session import get_session
from thesis_api.deps import get_tenant
from thesis_api.services.domains import ALL_DOMAINS, domains_for_level
from thesis_api.services.outbox import list_pending
from thesis_api.services.progress_store import event_to_public_dict
from thesis_api.tenant import TenantContext, TenantIsolationError

router = APIRouter(tags=["ui"])


def _assessment_or_404(
    row: AssessmentRow | None, tenant: TenantContext
) -> AssessmentRow:
    if row is None:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    try:
        tenant.assert_firm(row.firm_id)
    except TenantIsolationError as exc:
        raise HTTPException(status_code=404, detail="NOT_FOUND") from exc
    return row


def synthesize_domains(row: AssessmentRow) -> list[dict[str, Any]]:
    summary = row.summary_json or {}
    if isinstance(summary.get("domains"), list) and len(summary["domains"]) == 12:
        return summary["domains"]
    gates = summary.get("domain_gates") or {}
    active = set(domains_for_level(row.level))  # type: ignore[arg-type]
    out: list[dict[str, Any]] = []
    for d in ALL_DOMAINS:
        if d not in active:
            out.append(
                {
                    "domain_id": d,
                    "status": "skipped",
                    "gate_result": "unavailable_at_level",
                    "reason": f"Not in Level {row.level}",
                    "sources_found": 0,
                    "sources_required": 0,
                    "findings": 0,
                    "contradictions": 0,
                    "risks": 0,
                    "requests": 0,
                    "can_retry": False,
                }
            )
            continue
        gate = gates.get(d) or (
            "sufficient" if row.state in ("AWAITING_REVIEW", "COMPLETED", "DELIVERING") else "partial"
        )
        # Finished research uses "complete" so UI can label Cleared / Needs more / Open gap
        # from gate_result — never leave insufficient as status "partial".
        status = (
            "complete"
            if gate in ("sufficient", "partial", "insufficient", "not_applicable")
            else "partial"
        )
        if row.state in ("RESEARCHING", "PLANNING", "VALIDATING") and d not in gates:
            status = "running" if not gates else "pending"
            gate = gates.get(d) or "partial"
        out.append(
            {
                "domain_id": d,
                "status": status,
                "gate_result": gate,
                "reason": None,
                "sources_found": 1 if d in gates else 0,
                "sources_required": 1 if row.level == 1 else 2,
                "findings": 1 if d in gates else 0,
                "contradictions": 0,
                "risks": 0,
                "requests": 0,
                "can_retry": gate in ("insufficient", "partial"),
            }
        )
    return out


@router.get("/dashboard/summary")
async def dashboard_summary(
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(get_tenant),
) -> dict:
    rows = (
        await session.execute(
            select(AssessmentRow)
            .where(AssessmentRow.firm_id == tenant.firm_id)
            .order_by(AssessmentRow.created_at.desc())
        )
    ).scalars().all()
    active_states = {
        "CREATED",
        "PLANNING",
        "RESEARCHING",
        "VALIDATING",
        "EVALUATING",
        "CRITIQUING",
        "MEMO_READY",
        "AWAITING_REVIEW",
        "INFORMATION_REQUESTED",
        "DELIVERING",
    }
    active = [r for r in rows if r.state in active_states]
    pending_review = [r for r in rows if r.state == "AWAITING_REVIEW"]
    return {
        "kpis": {
            "active_assessments": len(active),
            "pending_decisions": len(pending_review),
            "completed": sum(1 for r in rows if r.state == "COMPLETED"),
            "watchlist": (
                await session.execute(
                    select(WatchlistEntryRow).where(
                        WatchlistEntryRow.firm_id == tenant.firm_id,
                        WatchlistEntryRow.paused.is_(False),
                    )
                )
            ).scalars().all().__len__(),
        },
        "pending_reviews": [
            {
                "assessment_id": r.id,
                "company_name": r.company_name,
                "level": r.level,
                "revision": r.revision,
                "headline": (r.summary_json or {}).get("headline"),
                "recommendation": (r.summary_json or {}).get("recommendation"),
                "review_target": (r.summary_json or {}).get("review_target"),
                "can_decide": True,
            }
            for r in pending_review
        ],
        "active_assessments": [
            {
                "assessment_id": r.id,
                "company_name": r.company_name,
                "level": r.level,
                "state": r.state,
                "revision": r.revision,
                "headline": (r.summary_json or {}).get("headline"),
                "recommendation": (r.summary_json or {}).get("recommendation"),
            }
            for r in active[:12]
        ],
        "recent_changes": [
            {
                "assessment_id": r.id,
                "company_name": r.company_name,
                "summary": (r.summary_json or {}).get("headline")
                or f"Moved to {r.state.replace('_', ' ').title()}",
                "when": r.created_at.isoformat() if r.created_at else None,
                "next": "Open assessment",
                "state": r.state,
            }
            for r in rows[:5]
        ],
    }


@router.get("/assessments/{assessment_id}/domains")
async def assessment_domains(
    assessment_id: str,
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(get_tenant),
) -> dict:
    row = (
        await session.execute(select(AssessmentRow).where(AssessmentRow.id == assessment_id))
    ).scalar_one_or_none()
    row = _assessment_or_404(row, tenant)
    domains = synthesize_domains(row)
    return {"items": domains, "total": len(domains)}


@router.get("/reviews")
async def list_reviews(
    status: str = Query(default="pending"),
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(get_tenant),
) -> dict:
    q = select(AssessmentRow).where(AssessmentRow.firm_id == tenant.firm_id)
    if status == "pending":
        q = q.where(AssessmentRow.state == "AWAITING_REVIEW")
    # Oldest first so partners clear the queue in arrival order.
    rows = (await session.execute(q.order_by(AssessmentRow.created_at.asc()))).scalars().all()
    items = []
    for r in rows:
        summary = r.summary_json or {}
        memo = summary.get("memo") if isinstance(summary.get("memo"), dict) else {}
        headline = summary.get("headline") or (memo.get("headline") if isinstance(memo, dict) else None)
        recommendation = summary.get("recommendation") or (
            memo.get("recommendation") if isinstance(memo, dict) else None
        )
        items.append(
            {
                "assessment_id": r.id,
                "company_name": r.company_name,
                "level": r.level,
                "revision": r.revision,
                "state": r.state,
                "headline": headline,
                "recommendation": recommendation,
                "conditions": summary.get("conditions") or [],
                "claim_total": summary.get("claim_total"),
                "llm_used": bool(summary.get("llm_used") or (memo.get("llm_used") if isinstance(memo, dict) else False)),
                "target": summary.get("review_target"),
                "target_digest": r.review_target_digest,
                "can_decide": "partner" in tenant.roles
                or "admin" in tenant.roles
                or "owner" in tenant.roles
                or "demo" in str(tenant.roles)
                or tenant.is_demo_session,
            }
        )
    return {"items": items, "total": len(items)}


@router.get("/ops/runs")
async def ops_runs(
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(get_tenant),
) -> dict:
    if not any(r in tenant.roles for r in ("operator", "admin", "owner", "partner")) and not tenant.is_demo_session:
        raise HTTPException(status_code=403, detail="FORBIDDEN")
    from thesis_api.services.workflow_reconcile import reconcile_assessment

    rows = (
        await session.execute(
            select(AssessmentRow)
            .where(AssessmentRow.firm_id == tenant.firm_id)
            .order_by(AssessmentRow.created_at.desc())
            .limit(50)
        )
    ).scalars().all()
    healed: list[dict] = []
    for r in rows:
        result = await reconcile_assessment(session, r)
        if result.get("changed"):
            healed.append(result)
    if healed:
        await session.commit()
    return {
        "items": [
            {
                "assessment_id": r.id,
                "company_name": r.company_name,
                "level": r.level,
                "state": r.state,
                "revision": r.revision,
                "workflow_id": r.workflow_id,
            }
            for r in rows
        ],
        "reconciled": healed,
    }


@router.get("/ops/attention")
async def ops_attention(
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(get_tenant),
) -> dict:
    if not any(r in tenant.roles for r in ("operator", "admin", "owner", "partner")) and not tenant.is_demo_session:
        raise HTTPException(status_code=403, detail="FORBIDDEN")
    pending = await list_pending(session, firm_id=tenant.firm_id, limit=20)
    blocked = (
        await session.execute(
            select(AssessmentRow).where(
                AssessmentRow.firm_id == tenant.firm_id,
                AssessmentRow.state.in_(
                    ["BLOCKED_CONFIGURATION", "BUDGET_EXHAUSTED", "INFORMATION_REQUESTED", "AWAITING_REVIEW"]
                ),
            )
        )
    ).scalars().all()
    return {
        "outbox_pending": len(pending),
        "blocked_or_waiting": [
            {
                "assessment_id": r.id,
                "company_name": r.company_name,
                "state": r.state,
            }
            for r in blocked
        ],
    }


@router.get("/ops/events")
async def ops_events(
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(get_tenant),
    limit: int = Query(default=30, ge=1, le=100),
) -> dict:
    """Recent durable progress events for Agent console LiveEventTail."""
    if not any(r in tenant.roles for r in ("operator", "admin", "owner", "partner")) and not tenant.is_demo_session:
        raise HTTPException(status_code=403, detail="FORBIDDEN")
    rows = (
        await session.execute(
            select(DomainProgressEventRow)
            .where(DomainProgressEventRow.firm_id == tenant.firm_id)
            .order_by(DomainProgressEventRow.event_id.desc())
            .limit(limit)
        )
    ).scalars().all()
    return {"items": [event_to_public_dict(r) for r in rows]}


@router.get("/companies")
async def list_companies(
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(get_tenant),
) -> dict:
    rows = (
        await session.execute(
            select(AssessmentRow)
            .where(AssessmentRow.firm_id == tenant.firm_id)
            .order_by(AssessmentRow.company_name.asc(), AssessmentRow.created_at.desc())
        )
    ).scalars().all()
    by_name: dict[str, AssessmentRow] = {}
    for r in rows:
        if r.company_name not in by_name:
            by_name[r.company_name] = r
    return {
        "items": [
            {
                "company_name": name,
                "latest_assessment_id": row.id,
                "level": row.level,
                "state": row.state,
                "revision": row.revision,
            }
            for name, row in sorted(by_name.items())
        ]
    }
