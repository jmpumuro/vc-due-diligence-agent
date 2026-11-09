"""Stage 7–8 outbox dispatch and retention scan activities."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from temporalio import activity

from thesis_api.db.models_stage6 import DataRoomRow, RetentionRecordRow
from thesis_api.db.session import SessionLocal
from thesis_api.services.outbox import dispatch_pending_local
from thesis_api.tenant_rls import activate_tenant_rls


@activity.defn(name="outbox_dispatch_pending")
async def outbox_dispatch_pending(firm_id: str | None = None) -> dict[str, Any]:
    async with SessionLocal() as session:
        if firm_id:
            await activate_tenant_rls(session, firm_id)
        result = await dispatch_pending_local(session, firm_id=firm_id)
        await session.commit()
        return {"ok": True, **result}


@activity.defn(name="retention_scan_due")
async def retention_scan_due(firm_id: str | None = None) -> dict[str, Any]:
    """List due rooms/records and emit a dry-run DeletionCertificate (D2 default)."""
    from thesis_api.services.retention import execute_deletion, plan_deletion

    now = datetime.now(timezone.utc)
    async with SessionLocal() as session:
        if firm_id:
            await activate_tenant_rls(session, firm_id)
        q = select(DataRoomRow).where(
            DataRoomRow.delete_after.is_not(None),
            DataRoomRow.delete_after <= now,
            DataRoomRow.legal_hold.is_(False),
        )
        if firm_id:
            q = q.where(DataRoomRow.firm_id == firm_id)
        rooms = list((await session.execute(q)).scalars().all())
        rq = select(RetentionRecordRow).where(
            RetentionRecordRow.delete_after.is_not(None),
            RetentionRecordRow.delete_after <= now,
            RetentionRecordRow.status == "active",
        )
        if firm_id:
            rq = rq.where(RetentionRecordRow.firm_id == firm_id)
        recs = list((await session.execute(rq)).scalars().all())
        from thesis_api.settings import settings

        room_ids = [r.data_room_id for r in rooms]
        rec_ids = [r.id for r in recs]
        bucket = settings.s3_bucket_dataroom
        object_keys = [
            f"s3://{bucket}/{r.object_prefix}*" for r in rooms if r.object_prefix
        ]
        cert = plan_deletion(
            firm_id=firm_id,
            data_room_ids=room_ids,
            retention_record_ids=rec_ids,
            object_keys=object_keys,
        )
        # Industry default: dry-run. execute_deletion no-ops unless flag set.
        cert = execute_deletion(cert)
        return {
            "ok": True,
            "due_data_rooms": [
                {
                    "data_room_id": r.data_room_id,
                    "assessment_id": r.assessment_id,
                    "delete_after": r.delete_after.isoformat() if r.delete_after else None,
                }
                for r in rooms
            ],
            "due_retention_records": [
                {"id": r.id, "data_room_id": r.data_room_id} for r in recs
            ],
            "destructive_delete": cert.mode == "executed",
            "deletion_certificate": cert.to_dict(),
        }
