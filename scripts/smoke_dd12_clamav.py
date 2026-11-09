#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Thesis contributors
"""DD-12/13 smoke: clean upload vs EICAR vs scanner-down (optional).

Requires running API with auth demo-session, L3 assessment + data room, healthy ClamAV.
Env:
  API_BASE (default http://127.0.0.1:8001)
  ASSESSMENT_ID (required for upload tests)
"""

from __future__ import annotations

import json
import os
import sys

import httpx

API = os.environ.get("API_BASE", "http://127.0.0.1:8001").rstrip("/")
AID = os.environ.get("ASSESSMENT_ID", "").strip()
EICAR = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"


def main() -> int:
    if not AID:
        print(json.dumps({"ok": False, "error": "ASSESSMENT_ID required"}))
        return 2
    client = httpx.Client(base_url=API, timeout=60.0, follow_redirects=True)
    client.post("/api/v1/auth/demo-session")
    results = []

    # Clean tiny PDF header bytes (not a full PDF — may parse_fail later; scan should be clean).
    clean = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
    r = client.post(
        f"/api/v1/assessments/{AID}/documents",
        files={"file": ("clean.pdf", clean, "application/pdf")},
    )
    results.append(
        {
            "name": "clean_upload",
            "status_code": r.status_code,
            "ok": r.status_code in (201, 200),
            "body": _safe(r),
        }
    )

    r = client.post(
        f"/api/v1/assessments/{AID}/documents",
        files={"file": ("eicar.com", EICAR, "application/octet-stream")},
    )
    detail = _safe(r).get("detail")
    results.append(
        {
            "name": "eicar_malware",
            "status_code": r.status_code,
            "ok": r.status_code == 422 and detail == "MALWARE_DETECTED",
            "body": _safe(r),
        }
    )

    report = {
        "passed": sum(1 for x in results if x["ok"]),
        "total": len(results),
        "results": results,
    }
    print(json.dumps(report, indent=2))
    return 0 if all(x["ok"] for x in results) else 1


def _safe(r: httpx.Response) -> dict:
    try:
        return r.json()
    except Exception:
        return {"text": r.text[:200]}


if __name__ == "__main__":
    raise SystemExit(main())
