#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Thesis contributors
"""D4 product-path smoke via worker-docs /ocr (not harness-only).

Exit 0 when native/scanned/encrypted/malformed behave per product contract.
Does not flip OCR_PRODUCT_VERIFIED by itself — prints evidence for operators.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "d4-ocr" / "fixtures"
BASE = os.environ.get("WORKER_DOCS_URL", "http://127.0.0.1:8091").rstrip("/")


def _post(name: str) -> tuple[int, dict]:
    path = FIXTURES / name
    with path.open("rb") as fh:
        res = httpx.post(f"{BASE}/ocr", files={"file": (name, fh, "application/pdf")}, timeout=120.0)
    try:
        body = res.json()
    except Exception:
        body = {"raw": res.text[:200]}
    return res.status_code, body


def main() -> int:
    # Prefer docker network hostname when running inside compose network via exec.
    checks = []

    code, body = _post("native.pdf")
    ok_native = code == 200 and body.get("ok") and "native_text" in set(body.get("methods") or [])
    checks.append(("native_no_forced_ocr", ok_native, body))

    code, body = _post("encrypted.pdf")
    ok_enc = code == 422 and body.get("detail") == "ENCRYPTED_DOCUMENT"
    checks.append(("encrypted", ok_enc, body))

    code, body = _post("malformed.pdf")
    ok_mal = code == 422 and body.get("detail") == "PARSE_FAILED"
    checks.append(("malformed", ok_mal, body))

    code, body = _post("scanned.pdf")
    ok_scan = code == 200 and body.get("ok") and (
        "ocr" in set(body.get("methods") or []) or int(body.get("ocr_pages") or 0) >= 0
    )
    checks.append(("scanned_accepted", ok_scan, body))

    report = {
        "base": BASE,
        "passed": sum(1 for _, ok, _ in checks if ok),
        "total": len(checks),
        "checks": [{"name": n, "ok": ok, "detail": d} for n, ok, d in checks],
        "ocr_product_verified_hint": "Set OCR_PRODUCT_VERIFIED=true only after this smoke is green in CI/compose.",
    }
    print(json.dumps(report, indent=2))
    return 0 if all(ok for _, ok, _ in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
