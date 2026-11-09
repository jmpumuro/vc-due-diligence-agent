# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Thesis contributors
"""PostgreSQL RLS session helper — REM-P0-02 / Stage 8.

Call `activate_tenant_rls` at the start of request/activity DB work so policies
read `current_setting('app.firm_id')` under role `thesis_app`.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from thesis_api.settings import settings


async def set_tenant_guc(session: AsyncSession, firm_id: str) -> None:
    # SET LOCAL / set_config(..., true) is transaction-scoped; safe for pooling.
    await session.execute(text("SELECT set_config('app.firm_id', :fid, true)"), {"fid": firm_id})


async def set_app_role(session: AsyncSession) -> bool:
    """SET LOCAL ROLE thesis_app so firm_isolation policies apply.

    Returns False if role switch is disabled or unavailable (owner path still
    relies on TenantContext.assert_firm).
    """
    if not settings.enforce_rls_role:
        return False
    try:
        await session.execute(text("SET LOCAL ROLE thesis_app"))
        return True
    except Exception:  # noqa: BLE001
        return False


async def activate_tenant_rls(session: AsyncSession, firm_id: str) -> None:
    """Preferred entry: GUC first, then optional app role."""
    await set_tenant_guc(session, firm_id)
    await set_app_role(session)
