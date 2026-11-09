# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Thesis contributors
"""Live two-firm RLS isolation (REM-P0-02).

Requires Postgres with migrations applied and role `thesis_app`.
Run: `uv run python scripts/smoke_rls_two_firm.py`

Skips when `LIVE_RLS=0` or the database is unreachable.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from thesis_api.settings import settings


def _live_enabled() -> bool:
    return os.environ.get("LIVE_RLS", "1") not in {"0", "false", "False"}


async def _insert_assessment_claim(
    session: AsyncSession,
    *,
    firm_id: str,
    assessment_id: str,
    claim_id: str,
    statement: str,
) -> None:
    now = datetime.now(timezone.utc)
    await session.execute(
        text(
            """
            INSERT INTO assessments (id, firm_id, company_name, level, state, revision, summary_json, created_at)
            VALUES (:aid, :firm, :name, 1, 'CREATED', 1, '{}'::jsonb, :now)
            """
        ),
        {"aid": assessment_id, "firm": firm_id, "name": f"RLS {firm_id[-6:]}", "now": now},
    )
    await session.execute(
        text(
            """
            INSERT INTO claims (
              claim_id, firm_id, assessment_id, revision, domain_id, statement,
              claim_type, subject, trust_state, verification_status, confidence,
              evidence_quality, evidence_span_ids, snapshot_ids, created_at, updated_at
            ) VALUES (
              :cid, :firm, :aid, 1, 'company', :statement,
              'fact', :subject, 'supported', 'unverified', 0.5,
              'mixed', '[]'::jsonb, '[]'::jsonb, :now, :now
            )
            """
        ),
        {
            "cid": claim_id,
            "firm": firm_id,
            "aid": assessment_id,
            "statement": statement,
            "subject": statement,
            "now": now,
        },
    )


async def _run_two_firm() -> None:
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    firm_a = f"frm_rls_a_{uuid.uuid4().hex[:8]}"
    firm_b = f"frm_rls_b_{uuid.uuid4().hex[:8]}"
    aid_a = str(uuid.uuid4())
    aid_b = str(uuid.uuid4())
    cid_a = str(uuid.uuid4())
    cid_b = str(uuid.uuid4())
    try:
        async with factory() as session:
            await session.execute(text("SELECT 1"))
            await _insert_assessment_claim(
                session, firm_id=firm_a, assessment_id=aid_a, claim_id=cid_a, statement="A secret"
            )
            await _insert_assessment_claim(
                session, firm_id=firm_b, assessment_id=aid_b, claim_id=cid_b, statement="B secret"
            )
            await session.commit()

            try:
                async with session.begin():
                    await session.execute(text("SET LOCAL ROLE thesis_app"))
                    await session.execute(
                        text("SELECT set_config('app.firm_id', :fid, true)"), {"fid": firm_a}
                    )
                    rows = (
                        await session.execute(
                            text(
                                "SELECT firm_id, statement FROM claims "
                                "WHERE claim_id = :a OR claim_id = :b"
                            ),
                            {"a": cid_a, "b": cid_b},
                        )
                    ).all()
                    firms = {r[0] for r in rows}
                    statements = {r[1] for r in rows}
                    assert firms == {firm_a}, f"expected only firm A, got {firms}"
                    assert "A secret" in statements
                    assert "B secret" not in statements

                    await session.execute(
                        text("SELECT set_config('app.firm_id', :fid, true)"), {"fid": firm_b}
                    )
                    rows_b = (
                        await session.execute(
                            text(
                                "SELECT firm_id, statement FROM claims "
                                "WHERE claim_id = :a OR claim_id = :b"
                            ),
                            {"a": cid_a, "b": cid_b},
                        )
                    ).all()
                    firms_b = {r[0] for r in rows_b}
                    statements_b = {r[1] for r in rows_b}
                    assert firms_b == {firm_b}, f"expected only firm B, got {firms_b}"
                    assert "B secret" in statements_b
                    assert "A secret" not in statements_b
            finally:
                await session.execute(text("RESET ROLE"))
                await session.execute(
                    text("DELETE FROM claims WHERE claim_id = :a OR claim_id = :b"),
                    {"a": cid_a, "b": cid_b},
                )
                await session.execute(
                    text("DELETE FROM assessments WHERE id = :a OR id = :b"),
                    {"a": aid_a, "b": aid_b},
                )
                await session.commit()
    finally:
        await engine.dispose()


async def _run_empty_guc() -> None:
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    firm = f"frm_rls_empty_{uuid.uuid4().hex[:8]}"
    aid = str(uuid.uuid4())
    cid = str(uuid.uuid4())
    try:
        async with factory() as session:
            await session.execute(text("SELECT 1"))
            await _insert_assessment_claim(
                session, firm_id=firm, assessment_id=aid, claim_id=cid, statement="hidden"
            )
            await session.commit()
            try:
                async with session.begin():
                    await session.execute(text("SET LOCAL ROLE thesis_app"))
                    await session.execute(text("SELECT set_config('app.firm_id', '', true)"))
                    n = (
                        await session.execute(
                            text("SELECT count(*) FROM claims WHERE claim_id = :cid"),
                            {"cid": cid},
                        )
                    ).scalar()
                    assert int(n or 0) == 0
            finally:
                await session.execute(text("RESET ROLE"))
                await session.execute(
                    text("DELETE FROM claims WHERE claim_id = :cid"), {"cid": cid}
                )
                await session.execute(
                    text("DELETE FROM assessments WHERE id = :aid"), {"aid": aid}
                )
                await session.commit()
    finally:
        await engine.dispose()


def test_thesis_app_role_cannot_see_other_firm_claims() -> None:
    if not _live_enabled():
        pytest.skip("LIVE_RLS disabled")
    try:
        asyncio.run(_run_two_firm())
    except Exception as exc:  # noqa: BLE001
        if "Connect" in type(exc).__name__ or "could not connect" in str(exc).lower():
            pytest.skip(f"postgres unavailable: {exc}")
        raise


def test_missing_firm_guc_sees_nothing_under_thesis_app() -> None:
    if not _live_enabled():
        pytest.skip("LIVE_RLS disabled")
    try:
        asyncio.run(_run_empty_guc())
    except Exception as exc:  # noqa: BLE001
        if "Connect" in type(exc).__name__ or "could not connect" in str(exc).lower():
            pytest.skip(f"postgres unavailable: {exc}")
        raise
