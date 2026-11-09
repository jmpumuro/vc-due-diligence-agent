# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Thesis contributors
"""HTTP client for worker-docs parse/OCR."""

from __future__ import annotations

from typing import Any

import httpx

from thesis_api.settings import settings


async def parse_pdf(data: bytes, filename: str = "upload.pdf") -> dict[str, Any]:
    """POST bytes to worker-docs /ocr. Returns ok=False on transport/HTTP errors."""
    url = settings.worker_docs_url.rstrip("/") + "/ocr"
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            res = await client.post(
                url,
                files={"file": (filename, data, "application/pdf")},
            )
            body: dict[str, Any]
            if res.headers.get("content-type", "").startswith("application/json"):
                body = res.json()
            else:
                body = {"detail": res.text[:200]}
            if res.status_code >= 400:
                return {
                    "ok": False,
                    "status_code": res.status_code,
                    "error": body.get("detail") or body.get("error") or f"http_{res.status_code}",
                }
            body["ok"] = True
            return body
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)[:200]}


async def harness_self_test() -> dict[str, Any]:
    url = settings.worker_docs_url.rstrip("/") + "/harness/self-test"
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            res = await client.get(url)
            body = res.json() if res.headers.get("content-type", "").startswith("application/json") else {}
            ok = res.status_code == 200 and bool(body.get("ok"))
            return {
                "ok": ok,
                "status_code": res.status_code,
                "methods": body.get("methods"),
                "page_count": body.get("page_count"),
                "error": None if ok else body.get("error") or f"http_{res.status_code}",
            }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)[:200]}
