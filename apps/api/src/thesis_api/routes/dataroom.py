# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Thesis contributors
"""Data-room create/list + ClamAV-gated document upload."""

from __future__ import annotations

import hashlib
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from thesis_api.db.models import AssessmentRow
from thesis_api.db.models_stage6 import DataRoomRow, DocumentRow
from thesis_api.db.session import get_session
from thesis_api.deps import get_tenant
from thesis_api.services.clamav import ping_clamav, scan_bytes
from thesis_api.services.object_store import put_bytes
from thesis_api.settings import settings
from thesis_api.tenant import TenantContext, TenantIsolationError

router = APIRouter(tags=["dataroom"])


def _clean_text(value: str | None, limit: int = 2000) -> str | None:
    """Strip NULs (clamd replies are NUL-terminated) for Postgres text columns."""
    if value is None:
        return None
    return value.replace("\x00", "").strip()[:limit] or None


async def _assessment(
    session: AsyncSession, tenant: TenantContext, assessment_id: str
) -> AssessmentRow:
    row = (
        await session.execute(select(AssessmentRow).where(AssessmentRow.id == assessment_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    try:
        tenant.assert_firm(row.firm_id)
    except TenantIsolationError as exc:
        raise HTTPException(status_code=404, detail="NOT_FOUND") from exc
    return row


class DataRoomCreate(BaseModel):
    note: str | None = Field(default=None, max_length=500)


@router.get("/assessments/{assessment_id}/data-room")
async def get_data_room(
    assessment_id: str,
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(get_tenant),
) -> dict:
    assessment = await _assessment(session, tenant, assessment_id)
    if assessment.level >= 3 and not tenant.may_access_private(assessment_id):
        if "partner" not in tenant.roles and "admin" not in tenant.roles and "owner" not in tenant.roles:
            raise HTTPException(status_code=403, detail="NOT_ON_DEAL_TEAM")
    row = (
        await session.execute(
            select(DataRoomRow).where(
                DataRoomRow.firm_id == tenant.firm_id,
                DataRoomRow.assessment_id == assessment_id,
            )
        )
    ).scalar_one_or_none()
    clam = await ping_clamav()
    if row is None:
        return {
            "exists": False,
            "assessment_id": assessment_id,
            "upload_enabled": bool(clam.get("ok")),
            "scan_enabled": bool(clam.get("ok")),
            "ocr_verified": False,
        }
    return {
        "exists": True,
        "data_room_id": row.data_room_id,
        "status": row.status,
        "object_prefix": row.object_prefix,
        "legal_hold": row.legal_hold,
        "delete_after": row.delete_after.isoformat() if row.delete_after else None,
        "upload_enabled": bool(clam.get("ok")),
        "scan_enabled": bool(clam.get("ok")),
        "ocr_verified": False,
        "notice": (
            "ClamAV online; OCR product Verified still open (worker-docs health only)."
            if clam.get("ok")
            else "Upload/ClamAV unavailable — SCANNER_UNAVAILABLE until clamd is healthy."
        ),
    }


@router.post("/assessments/{assessment_id}/data-room", status_code=201)
async def create_data_room(
    assessment_id: str,
    body: DataRoomCreate | None = None,
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(get_tenant),
) -> dict:
    if "partner" not in tenant.roles and "admin" not in tenant.roles and "owner" not in tenant.roles:
        raise HTTPException(status_code=403, detail="FORBIDDEN")
    assessment = await _assessment(session, tenant, assessment_id)
    existing = (
        await session.execute(
            select(DataRoomRow).where(
                DataRoomRow.firm_id == tenant.firm_id,
                DataRoomRow.assessment_id == assessment_id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return {
            "data_room_id": existing.data_room_id,
            "status": existing.status,
            "object_prefix": existing.object_prefix,
            "created": False,
        }

    prefix = f"{tenant.firm_id}/{assessment_id}/"
    row = DataRoomRow(
        data_room_id=str(uuid4()),
        firm_id=tenant.firm_id,
        assessment_id=assessment_id,
        status="open",
        object_prefix=prefix,
        legal_hold=False,
    )
    session.add(row)
    await session.commit()
    return {
        "data_room_id": row.data_room_id,
        "status": row.status,
        "object_prefix": row.object_prefix,
        "bucket": settings.s3_bucket_dataroom,
        "created": True,
        "note": (body.note if body else None),
        "upload_enabled": bool((await ping_clamav()).get("ok")),
    }


@router.get("/assessments/{assessment_id}/documents")
async def list_documents(
    assessment_id: str,
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(get_tenant),
) -> dict:
    assessment = await _assessment(session, tenant, assessment_id)
    if assessment.level >= 3 and not tenant.may_access_private(assessment_id):
        if not any(r in tenant.roles for r in ("partner", "admin", "owner")):
            raise HTTPException(status_code=403, detail="NOT_ON_DEAL_TEAM")
    rows = (
        await session.execute(
            select(DocumentRow)
            .where(
                DocumentRow.firm_id == tenant.firm_id,
                DocumentRow.assessment_id == assessment_id,
            )
            .order_by(DocumentRow.created_at.desc())
        )
    ).scalars().all()
    return {
        "items": [
            {
                "document_id": r.document_id,
                "filename": r.filename,
                "status": r.status,
                "byte_size": r.byte_size,
                "sha256": r.sha256,
                "object_bucket": r.object_bucket,
                "scan_detail": r.scan_detail,
                "ocr_pages": r.ocr_pages,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    }


@router.post("/assessments/{assessment_id}/documents", status_code=201)
async def upload_document(
    assessment_id: str,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(get_tenant),
) -> dict:
    """Scan with ClamAV then store. Malware → quarantine + MALWARE_DETECTED."""
    assessment = await _assessment(session, tenant, assessment_id)
    if assessment.level < 3:
        raise HTTPException(status_code=409, detail="LEVEL3_REQUIRED")
    if not tenant.may_access_private(assessment_id) and not any(
        r in tenant.roles for r in ("partner", "admin", "owner")
    ):
        raise HTTPException(status_code=403, detail="NOT_ON_DEAL_TEAM")

    room = (
        await session.execute(
            select(DataRoomRow).where(
                DataRoomRow.firm_id == tenant.firm_id,
                DataRoomRow.assessment_id == assessment_id,
            )
        )
    ).scalar_one_or_none()
    if room is None:
        raise HTTPException(status_code=409, detail="DATA_ROOM_REQUIRED")

    clam = await ping_clamav()
    if not clam.get("ok"):
        raise HTTPException(status_code=503, detail="SCANNER_UNAVAILABLE")

    raw = await file.read()
    if len(raw) > settings.docs_max_upload_bytes:
        raise HTTPException(status_code=413, detail="LIMIT_EXCEEDED")
    if not raw:
        raise HTTPException(status_code=422, detail="EMPTY_UPLOAD")

    filename = (file.filename or "upload.bin")[:512]
    digest = hashlib.sha256(raw).hexdigest()
    scan = await scan_bytes(raw)
    doc_id = str(uuid4())
    key = f"{room.object_prefix}{doc_id}/{filename}"

    if scan.status == "unavailable":
        raise HTTPException(status_code=503, detail="SCANNER_UNAVAILABLE")
    if scan.status == "malware":
        put_bytes(
            bucket=settings.s3_bucket_quarantine,
            key=key,
            data=raw,
            content_type=file.content_type or "application/octet-stream",
        )
        row = DocumentRow(
            document_id=doc_id,
            firm_id=tenant.firm_id,
            assessment_id=assessment_id,
            data_room_id=room.data_room_id,
            filename=filename,
            content_type=file.content_type,
            byte_size=len(raw),
            sha256=digest,
            status="quarantined",
            object_bucket=settings.s3_bucket_quarantine,
            object_key=key,
            scan_detail=_clean_text(scan.detail),
        )
        session.add(row)
        await session.commit()
        raise HTTPException(
            status_code=422,
            detail="MALWARE_DETECTED",
        )

    if scan.status != "clean" and scan.status != "empty":
        raise HTTPException(status_code=503, detail="SCANNER_UNAVAILABLE")

    put_bytes(
        bucket=settings.s3_bucket_dataroom,
        key=key,
        data=raw,
        content_type=file.content_type or "application/octet-stream",
    )

    is_pdf = (
        filename.lower().endswith(".pdf")
        or (file.content_type or "").lower().endswith("pdf")
        or raw[:4] == b"%PDF"
    )
    status = "parsing" if is_pdf else "ready"
    scan_note = _clean_text(scan.detail) or "clean"
    if is_pdf:
        scan_note = _clean_text(f"{scan_note}; queued q.docs") or scan_note

    row = DocumentRow(
        document_id=doc_id,
        firm_id=tenant.firm_id,
        assessment_id=assessment_id,
        data_room_id=room.data_room_id,
        filename=filename,
        content_type=file.content_type,
        byte_size=len(raw),
        sha256=digest,
        status=status,
        object_bucket=settings.s3_bucket_dataroom,
        object_key=key,
        scan_detail=scan_note,
        ocr_pages=None,
    )
    session.add(row)
    await session.commit()

    workflow_id = None
    if is_pdf:
        try:
            from temporalio.client import Client

            from thesis_api.temporal_app.workflows import DocumentIngestionWorkflow

            client = await Client.connect(settings.temporal_host)
            workflow_id = f"doc:{tenant.firm_id}:{doc_id}:v1"
            await client.start_workflow(
                DocumentIngestionWorkflow.run,
                {"firm_id": tenant.firm_id, "document_id": doc_id},
                id=workflow_id,
                task_queue="q.docs",
            )
        except Exception as exc:  # noqa: BLE001 — leave status parsing; surface notice
            row.scan_detail = _clean_text(f"{scan_note}; workflow_start_failed:{exc}")
            await session.commit()
            workflow_id = None

    return {
        "document_id": doc_id,
        "filename": filename,
        "status": status,
        "sha256": digest,
        "byte_size": len(raw),
        "object_bucket": settings.s3_bucket_dataroom,
        "object_key": key,
        "workflow_id": workflow_id,
        "ocr_verified": settings.ocr_product_verified,
        "notice": (
            "Stored after ClamAV clean scan; PDF queued on Temporal q.docs for parse/OCR."
            if is_pdf
            else "Stored after ClamAV clean scan. Non-PDF parse not yet wired."
        ),
    }
