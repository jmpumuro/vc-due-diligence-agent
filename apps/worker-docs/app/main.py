# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Thesis contributors
"""worker-docs: health + PDF native/OCR extract (D4 harness product path)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

app = FastAPI(title="Thesis worker-docs", version="0.2.0")

HARNESS_ROOT = Path(os.environ.get("HARNESS_ROOT", "/app/fixtures/d4-ocr"))
if str(HARNESS_ROOT) not in sys.path:
    sys.path.insert(0, str(HARNESS_ROOT))


def _tesseract_version() -> str | None:
    bin_path = shutil.which("tesseract")
    if not bin_path:
        return None
    try:
        out = subprocess.check_output([bin_path, "--version"], stderr=subprocess.STDOUT, text=True)
        return out.splitlines()[0].strip() if out else "unknown"
    except (OSError, subprocess.CalledProcessError):
        return None


def _extract_pdf(pdf_bytes: bytes, *, max_ocr_pages: int = 200, langs: str | None = None) -> dict:
    from ocr_harness import EncryptedDocument, ParseFailed, extract  # type: ignore[import-not-found]

    langs = langs or os.environ.get("OCR_LANGUAGES", "eng")
    try:
        result = extract(pdf_bytes, max_ocr_pages=max_ocr_pages, langs=langs)
    except EncryptedDocument as exc:
        raise HTTPException(status_code=422, detail="ENCRYPTED_DOCUMENT") from exc
    except ParseFailed as exc:
        raise HTTPException(status_code=422, detail="PARSE_FAILED") from exc

    pages = [
        {
            "page": p.page,
            "method": p.method,
            "reason": p.reason,
            "chars": len(p.text or ""),
            "native_chars": p.native_chars,
            "image_coverage": p.image_coverage,
            "ocr_engine": p.ocr_engine,
            "ocr_language": p.ocr_language,
            "ocr_confidence": p.ocr_confidence,
            "low_confidence": p.low_confidence,
            "seconds": p.seconds,
            # Truncate page text in API responses; full text stays for product ingest later.
            "text_preview": (p.text or "")[:500],
        }
        for p in result.pages
    ]
    methods = {p["method"] for p in pages}
    return {
        "ok": True,
        "page_count": len(pages),
        "ocr_pages": sum(1 for p in pages if p["method"] == "ocr"),
        "methods": sorted(methods),
        "warnings": list(result.warnings),
        "pages": pages,
    }


@app.get("/health")
def health() -> dict:
    tess = _tesseract_version()
    langs = os.environ.get("OCR_LANGUAGES", "eng")
    return {
        "ok": bool(tess),
        "service": "worker-docs",
        "tesseract": tess,
        "ocr_languages": langs,
        "harness_path": str(HARNESS_ROOT),
        "status": "ready" if tess else "tesseract_missing",
        "ocr_endpoint": "/ocr",
        "notice": "Parse/OCR endpoint online; Temporal q.docs ingest still incremental.",
    }


@app.get("/health/live")
def live() -> dict:
    return {"ok": True}


@app.get("/harness/self-test")
def harness_self_test() -> dict:
    """Smoke the D4 native fixture through the product extract path."""
    native = HARNESS_ROOT / "fixtures" / "native.pdf"
    if not native.is_file():
        return JSONResponse(
            status_code=503,
            content={"ok": False, "error": "native_fixture_missing", "path": str(native)},
        )
    if not _tesseract_version():
        return JSONResponse(status_code=503, content={"ok": False, "error": "tesseract_missing"})
    try:
        result = _extract_pdf(native.read_bytes(), max_ocr_pages=2)
    except HTTPException as exc:
        return JSONResponse(
            status_code=503,
            content={"ok": False, "error": str(exc.detail)},
        )
    ok = result.get("page_count", 0) >= 1 and "native_text" in set(result.get("methods") or [])
    return {
        "ok": ok,
        "fixture": "native.pdf",
        "page_count": result.get("page_count"),
        "methods": result.get("methods"),
        "notice": "Harness smoke only — full D4 product Verified still open.",
    }


@app.post("/ocr")
async def ocr_pdf(
    file: UploadFile = File(...),
    max_ocr_pages: int = 50,
) -> dict:
    """Native-first PDF extract with Tesseract OCR fallback (D4 algorithm)."""
    if not _tesseract_version():
        raise HTTPException(status_code=503, detail="TESSERACT_MISSING")
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=422, detail="EMPTY_UPLOAD")
    name = (file.filename or "").lower()
    ctype = (file.content_type or "").lower()
    if not (name.endswith(".pdf") or "pdf" in ctype or raw[:4] == b"%PDF"):
        raise HTTPException(status_code=415, detail="PDF_REQUIRED")
    return _extract_pdf(raw, max_ocr_pages=max(1, min(max_ocr_pages, 200)))
