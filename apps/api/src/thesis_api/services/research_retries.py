"""Transactional retry results: evidence and completion commit together."""

import hashlib
import json

from sqlalchemy import text


def operation_key(firm_id: str, workflow_id: str, run_id: str, activity_id: str) -> str:
    return hashlib.sha256(json.dumps([firm_id, workflow_id, run_id, activity_id]).encode()).hexdigest()


async def completed_result(session, firm_id: str, operation: str):
    await session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {
        "key": int.from_bytes(bytes.fromhex(operation)[:8], "big", signed=True)
    })
    return (await session.execute(text(
        "SELECT result FROM research_activity_results WHERE operation_id=:id AND firm_id=:firm"
    ), {"id": operation, "firm": firm_id})).scalar_one_or_none()


async def remember_result(session, firm_id: str, assessment_id: str, operation: str, result):
    await session.execute(text(
        "INSERT INTO research_activity_results(operation_id, firm_id, assessment_id, result) "
        "VALUES (:id, :firm, :assessment, CAST(:result AS JSONB))"
    ), {"id": operation, "firm": firm_id, "assessment": assessment_id,
        "result": json.dumps(result, default=str)})
