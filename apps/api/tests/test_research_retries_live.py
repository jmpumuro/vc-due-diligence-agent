"""Real PostgreSQL concurrency/RLS checks for committed research retries."""

import asyncio
import os
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from thesis_api.services.research_retries import completed_result, operation_key, remember_result
from thesis_api.settings import settings
from thesis_api.tenant_rls import activate_tenant_rls


@pytest.mark.skipif(os.environ.get("LIVE_RLS", "0") != "1", reason="requires migrated PostgreSQL")
def test_retry_commit_rollback_concurrency_and_tenant_isolation():
    async def run():
        engine = create_async_engine(settings.database_url)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        assessment = str(uuid4())
        firm = "sandbox-" + uuid4().hex[:12]
        operation = operation_key(firm, "workflow", "run", "domain")
        writes = 0
        try:
            async with sessions() as session:
                await session.execute(text(
                    "INSERT INTO assessments(id,firm_id,company_name,level,state,revision,summary_json,created_at) "
                    "VALUES (:id,:firm,'Retry probe',1,'CREATED',1,'{}'::jsonb,now())"
                ), {"id": assessment, "firm": firm})
                await session.commit()
            # A failed transaction must not leave a successful retry marker.
            async with sessions() as session:
                await activate_tenant_rls(session, firm)
                assert await completed_result(session, firm, operation) is None
                await remember_result(session, firm, assessment, operation, {"claim":"rolled-back"})
                await session.rollback()

            async def attempt():
                nonlocal writes
                async with sessions() as session:
                    await activate_tenant_rls(session, firm)
                    prior = await completed_result(session, firm, operation)
                    if prior is not None:
                        return prior
                    writes += 1
                    await asyncio.sleep(0.05)
                    result = {"claim":"committed-once", "snapshot":"same-evidence"}
                    await remember_result(session, firm, assessment, operation, result)
                    await session.commit()
                    return result

            first, retry = await asyncio.gather(attempt(), attempt())
            assert first == retry and writes == 1
            async with sessions() as session:
                await activate_tenant_rls(session, "another-firm")
                rows = (await session.execute(text(
                    "SELECT * FROM research_activity_results WHERE operation_id=:id"
                ), {"id":operation})).all()
                assert rows == []
                with pytest.raises(DBAPIError):
                    await remember_result(session, firm, assessment, "wrong-tenant", {})
                await session.rollback()
                await activate_tenant_rls(session, "another-firm")
                with pytest.raises(DBAPIError):
                    await remember_result(session, "another-firm", assessment, "cross-assessment", {})
                await session.rollback()
            async with sessions() as session:
                await session.execute(text("DELETE FROM assessments WHERE id=:id"), {"id":assessment})
                assert (await session.execute(text(
                    "SELECT count(*) FROM research_activity_results WHERE operation_id=:id"
                ), {"id":operation})).scalar_one() == 0
                await session.commit()
        finally:
            async with sessions() as session:
                await session.execute(text("DELETE FROM assessments WHERE id=:id"), {"id":assessment})
                await session.commit()
            await engine.dispose()

    asyncio.run(run())
