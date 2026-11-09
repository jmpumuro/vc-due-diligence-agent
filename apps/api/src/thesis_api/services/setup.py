from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from thesis_api.db.models import AppUser, Firm, SetupToken, SystemFlag
from thesis_api.services.auth_crypto import hash_password, hash_setup_token, new_setup_token


async def is_setup_complete(db: AsyncSession) -> bool:
    flag = await db.get(SystemFlag, "setup_complete")
    return flag is not None and flag.value == "true"


async def ensure_setup_token(db: AsyncSession) -> str | None:
    """If setup incomplete, ensure a valid token exists and return the raw token once.

    Returns None when setup is already complete. When a fresh token is minted, the
    raw value is returned for logging; callers must not persist the raw token.
    """
    if await is_setup_complete(db):
        return None

    now = datetime.now(timezone.utc)
    existing = (
        await db.execute(
            select(SetupToken).where(SetupToken.used_at.is_(None), SetupToken.expires_at > now)
        )
    ).scalar_one_or_none()
    if existing is not None:
        # Token already issued this boot cycle; do not re-log raw value.
        return None

    raw, digest = new_setup_token()
    db.add(SetupToken(token_hash=digest, expires_at=now + timedelta(hours=24)))
    await db.commit()
    return raw


async def complete_setup(
    db: AsyncSession,
    *,
    token: str,
    firm_name: str,
    owner_email: str,
    owner_name: str,
    password: str,
) -> dict:
    if await is_setup_complete(db):
        raise ValueError("SETUP_ALREADY_COMPLETE")

    now = datetime.now(timezone.utc)
    digest = hash_setup_token(token)
    row = await db.get(SetupToken, digest)
    if row is None or row.used_at is not None or row.expires_at < now:
        raise ValueError("SETUP_TOKEN_INVALID")

    firm_id = f"frm_{uuid4().hex[:12]}"
    firm = Firm(id=firm_id, name=firm_name.strip())
    owner = AppUser(
        id=str(uuid4()),
        email=owner_email.strip().lower(),
        display_name=owner_name.strip(),
        firm_id=firm_id,
        roles=["owner", "admin"],
        is_demo=False,
        password_hash=hash_password(password),
    )
    row.used_at = now
    db.add(firm)
    db.add(owner)
    db.add(SystemFlag(key="setup_complete", value="true"))
    await db.commit()
    return {
        "firm_id": firm_id,
        "owner_user_id": owner.id,
        "edgar_user_agent_hint": f"{firm_name} diligence ({owner_email})",
    }
