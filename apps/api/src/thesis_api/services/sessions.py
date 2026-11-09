from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from thesis_api.db.models import SessionRow


async def create_session(
    db: AsyncSession,
    *,
    user_id: str,
    firm_id: str,
    is_demo: bool,
    lifetime: timedelta,
) -> SessionRow:
    row = SessionRow(
        id=str(uuid4()),
        user_id=user_id,
        firm_id=firm_id,
        is_demo=is_demo,
        expires_at=datetime.now(timezone.utc) + lifetime,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def delete_session(db: AsyncSession, session_id: str) -> None:
    row = await db.get(SessionRow, session_id)
    if row is not None:
        await db.delete(row)
        await db.commit()
