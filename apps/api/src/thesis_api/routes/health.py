from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from thesis_api.db.session import get_session
from thesis_api.services.readiness import health_ready

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def ready(session: AsyncSession = Depends(get_session)) -> JSONResponse:
    ok, payload = await health_ready(session)
    return JSONResponse(status_code=200 if ok else 503, content=payload)
