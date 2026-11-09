from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from thesis_api.db.models import AppUser, Firm
from thesis_api.db.session import get_session
from thesis_api.deps import SESSION_COOKIE, get_tenant
from thesis_api.services.auth_crypto import verify_password
from thesis_api.services.sessions import create_session, delete_session
from thesis_api.services.setup import complete_setup, is_setup_complete
from thesis_api.settings import settings
from thesis_api.tenant import TenantContext

router = APIRouter(tags=["auth"])


class SetupBody(BaseModel):
    token: str = Field(min_length=8)
    firm_name: str = Field(min_length=2, max_length=255)
    owner_email: EmailStr
    owner_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=10, max_length=200)


class LoginBody(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


def _set_session_cookie(response: Response, session_id: str, *, max_age: int) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        session_id,
        httponly=True,
        samesite="lax",
        secure=settings.app_env not in ("development", "test"),
        max_age=max_age,
        path="/",
    )


@router.get("/setup/status")
async def setup_status(session: AsyncSession = Depends(get_session)) -> dict:
    return {"setup_complete": await is_setup_complete(session)}


@router.post("/setup")
async def setup(body: SetupBody, session: AsyncSession = Depends(get_session)) -> dict:
    try:
        result = await complete_setup(
            session,
            token=body.token,
            firm_name=body.firm_name,
            owner_email=str(body.owner_email),
            owner_name=body.owner_name,
            password=body.password,
        )
    except ValueError as exc:
        code = str(exc)
        status = 409 if code == "SETUP_ALREADY_COMPLETE" else 400
        raise HTTPException(status_code=status, detail=code) from exc
    return {"ok": True, **result}


@router.post("/auth/login")
async def login(
    body: LoginBody,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> dict:
    user = (
        await session.execute(select(AppUser).where(AppUser.email == str(body.email).lower()))
    ).scalar_one_or_none()
    if user is None or not user.password_hash or not verify_password(user.password_hash, body.password):
        raise HTTPException(status_code=401, detail="INVALID_CREDENTIALS")
    if user.is_demo:
        raise HTTPException(status_code=403, detail="DEMO_USER_NO_PASSWORD_LOGIN")
    row = await create_session(
        session,
        user_id=user.id,
        firm_id=user.firm_id,
        is_demo=False,
        lifetime=timedelta(days=7),
    )
    _set_session_cookie(response, row.id, max_age=7 * 24 * 3600)
    return {"ok": True, "user_id": user.id, "firm_id": user.firm_id}


@router.post("/auth/logout")
async def logout(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> dict:
    sid = request.cookies.get(SESSION_COOKIE)
    if sid:
        await delete_session(session, sid)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@router.post("/auth/demo-session")
async def demo_session(response: Response, session: AsyncSession = Depends(get_session)) -> dict:
    if not settings.demo_workspace:
        raise HTTPException(status_code=404, detail="DEMO_DISABLED")
    user = (
        await session.execute(select(AppUser).where(AppUser.email == "demo@thesis.local"))
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=503, detail="DEMO_NOT_SEEDED")
    row = await create_session(
        session,
        user_id=user.id,
        firm_id="frm_demo",
        is_demo=True,
        lifetime=timedelta(hours=4),
    )
    _set_session_cookie(response, row.id, max_age=4 * 3600)
    return {"ok": True, "user_id": user.id}


@router.get("/me")
async def me(
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(get_tenant),
) -> dict:
    user = (
        await session.execute(select(AppUser).where(AppUser.id == tenant.user_id))
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="UNAUTHENTICATED")
    firm = await session.get(Firm, tenant.firm_id)
    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "roles": user.roles,
            "is_demo": user.is_demo,
        },
        "firm": {"id": tenant.firm_id, "name": firm.name if firm else tenant.firm_id},
        "roles": list(tenant.roles),
        "is_demo_session": tenant.is_demo_session,
    }
