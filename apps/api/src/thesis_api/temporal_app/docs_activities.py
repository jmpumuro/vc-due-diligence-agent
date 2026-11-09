# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Thesis contributors
"""q.docs DocumentIngestion activities."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from temporalio import activity

from thesis_api.db.models_stage6 import DocumentRow
from thesis_api.db.session import SessionLocal
from thesis_api.tenant_rls import activate_tenant_rls


@activity.defn(name="docs_mark_status")
async def docs_mark_status(
    firm_id: str,
    document_id: str,
    status: str,
    scan_detail: str | None = None,
    ocr_pages: int | None = None,
) -> dict[str, Any]:
    async with SessionLocal() as session:
        await activate_tenant_rls(session, firm_id)
        row = (
            await session.execute(select(DocumentRow).where(DocumentRow.document_id == document_id))
        ).scalar_one_or_none()
        if row is None:
            return {"ok": False, "error": "NOT_FOUND"}
        row.status = status
        if scan_detail is not None:
            row.scan_detail = scan_detail.replace("\x00", "").strip()[:2000]
        if ocr_pages is not None:
            row.ocr_pages = ocr_pages
        await session.commit()
        return {"ok": True, "document_id": document_id, "status": status}


@activity.defn(name="docs_fetch_and_parse")
async def docs_fetch_and_parse(
    firm_id: str,
    document_id: str,
) -> dict[str, Any]:
    """Load object bytes and parse PDFs via worker-docs."""
    from thesis_api.services.object_store import get_bytes
    from thesis_api.services.worker_docs import parse_pdf

    async with SessionLocal() as session:
        await activate_tenant_rls(session, firm_id)
        row = (
            await session.execute(select(DocumentRow).where(DocumentRow.document_id == document_id))
        ).scalar_one_or_none()
        if row is None:
            return {"ok": False, "error": "NOT_FOUND"}
        bucket = row.object_bucket
        key = row.object_key
        filename = row.filename
        content_type = row.content_type or ""

    try:
        raw = get_bytes(bucket=bucket, key=key)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"FETCH_FAILED:{exc}"[:200]}

    is_pdf = (
        filename.lower().endswith(".pdf")
        or "pdf" in content_type.lower()
        or raw[:4] == b"%PDF"
    )
    if not is_pdf:
        return {
            "ok": True,
            "status": "ready",
            "ocr_pages": None,
            "detail": "non_pdf_stored_without_parse",
        }

    parsed = await parse_pdf(raw, filename=filename)
    if not parsed.get("ok"):
        return {
            "ok": False,
            "status": "parse_failed",
            "error": str(parsed.get("error") or "PARSE_FAILED")[:500],
        }
    methods = ",".join(parsed.get("methods") or [])
    return {
        "ok": True,
        "status": "ready",
        "ocr_pages": int(parsed.get("ocr_pages") or 0),
        "detail": f"q.docs pages={parsed.get('page_count')} methods={methods}",
        "methods": parsed.get("methods"),
        "page_count": parsed.get("page_count"),
    }
