from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from thesis_api.db.models import AssessmentRow
from thesis_api.db.session import get_session
from thesis_api.deps import get_tenant
from thesis_api.services.assessment_view import enrich_assessment_payload
from thesis_api.tenant import TenantContext, TenantIsolationError

router = APIRouter(tags=["assessments"])


@router.get("/assessments")
async def list_assessments(
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(get_tenant),
) -> dict:
    rows = (
        await session.execute(
            select(AssessmentRow)
            .where(AssessmentRow.firm_id == tenant.firm_id)
            .order_by(AssessmentRow.created_at)
        )
    ).scalars()
    items = [
        {
            "assessment_id": r.id,
            "firm_id": r.firm_id,
            "company_name": r.company_name,
            "level": r.level,
            "state": r.state,
            "revision": r.revision,
            "summary": r.summary_json,
        }
        for r in rows
    ]
    return {"items": items, "next_cursor": None, "total": len(items)}


@router.get("/assessments/{assessment_id}")
async def get_assessment(
    assessment_id: str,
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(get_tenant),
) -> dict:
    row = (
        await session.execute(select(AssessmentRow).where(AssessmentRow.id == assessment_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    try:
        tenant.assert_firm(row.firm_id)
    except TenantIsolationError as exc:
        raise HTTPException(status_code=404, detail="NOT_FOUND") from exc
    return await enrich_assessment_payload(session, tenant, row)
