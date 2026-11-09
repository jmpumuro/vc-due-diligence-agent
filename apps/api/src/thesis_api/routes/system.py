from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from thesis_api.db.session import get_session
from thesis_api.services.readiness import system_status

router = APIRouter(tags=["system"])


@router.get("/system/status")
async def status(session: AsyncSession = Depends(get_session)) -> dict:
    return await system_status(session)
