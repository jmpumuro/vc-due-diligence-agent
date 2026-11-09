"""Shared FastAPI dependencies — session → TenantContext (REM-P0-02)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Cookie, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from thesis_api.db.models import AppUser, SessionRow
from thesis_api.db.models_stage6 import DealTeamMemberRow
from thesis_api.db.session import get_session
from thesis_api.settings import settings
from thesis_api.tenant import TenantContext
from thesis_api.tenant_rls import activate_tenant_rls

SESSION_COOKIE = "thesis_session"


async def _deal_team_ids(session: AsyncSession, *, firm_id: str, user_id: str) -> frozenset[str]:
    rows = (
        await session.execute(
            select(DealTeamMemberRow.assessment_id).where(
                DealTeamMemberRow.firm_id == firm_id,
                DealTeamMemberRow.user_id == user_id,
            )
        )
    ).scalars().all()
    return frozenset(str(a) for a in rows)


async def get_tenant(
    request: Request,
    session: AsyncSession = Depends(get_session),
    thesis_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> TenantContext:
    if not thesis_session:
        raise HTTPException(status_code=401, detail="UNAUTHENTICATED")

    row = (
        await session.execute(select(SessionRow).where(SessionRow.id == thesis_session))
    ).scalar_one_or_none()
    if row is None or row.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="SESSION_EXPIRED")

    user = (
        await session.execute(select(AppUser).where(AppUser.id == row.user_id))
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="UNAUTHENTICATED")

    # Demo sessions cannot escalate or leave frm_demo.
    if row.is_demo and (user.firm_id != "frm_demo" or not settings.demo_workspace):
        raise HTTPException(status_code=403, detail="DEMO_SESSION_RESTRICTED")

    await activate_tenant_rls(session, row.firm_id)
    deal_ids = await _deal_team_ids(session, firm_id=row.firm_id, user_id=user.id)

    return TenantContext(
        firm_id=row.firm_id,
        user_id=user.id,
        roles=tuple(user.roles or ()),
        is_demo_session=row.is_demo,
        deal_team_assessment_ids=deal_ids,
    )
