#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Thesis contributors
"""Live E2E across Level 1–3 for a real company (OpenAI key required).

L1/L2: full Temporal screening → AWAITING_REVIEW + claims/contradictions.
L3: create shell + data-room; ClamAV upload when healthy; screening stays
fail-closed until OCR_PRODUCT_VERIFIED / private pipeline gates lift.
"""

from __future__ import annotations

import http.cookiejar
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API = os.environ.get("PUBLIC_API_URL", "http://localhost:8001").rstrip("/")
WEB = os.environ.get("PUBLIC_WEB_URL", "http://localhost:3000").rstrip("/")
COMPANY = os.environ.get("E2E_COMPANY", "Stripe")
OUT = Path(os.environ.get("E2E_OUT", "/tmp/thesis_e2e_all_levels.json"))
FIXTURE_PDF = Path(
    os.environ.get(
        "E2E_PDF",
        str(Path(__file__).resolve().parents[1] / "fixtures" / "d4-ocr" / "fixtures" / "native.pdf"),
    )
)


def opener():
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def call(op, method: str, path: str, data: dict | None = None):
    body = None if data is None else json.dumps(data).encode()
    req = urllib.request.Request(
        f"{API}{path}",
        data=body,
        headers={"content-type": "application/json", "Idempotency-Key": f"e2e-{time.time_ns()}"},
        method=method,
    )
    try:
        with op.open(req, timeout=120) as res:
            raw = res.read().decode()
            return res.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"raw": raw}


def upload(op, aid: str, path: Path):
    boundary = f"----thesis{time.time_ns()}"
    data = path.read_bytes()
    parts = [
        f"--{boundary}\r\n".encode(),
        (
            f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
            f"Content-Type: application/pdf\r\n\r\n"
        ).encode(),
        data,
        f"\r\n--{boundary}--\r\n".encode(),
    ]
    body = b"".join(parts)
    req = urllib.request.Request(
        f"{API}/api/v1/assessments/{aid}/documents",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with op.open(req, timeout=180) as res:
            raw = res.read().decode()
            return res.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"raw": raw}


def run_public_level(op, level: int, timeout_s: int) -> dict:
    print(f"\n=== Level {level} · {COMPANY} ===")
    code, created = call(
        op,
        "POST",
        "/api/v1/assessments",
        {"company_name": COMPANY, "level": level, "start_screening": True},
    )
    aid = created.get("assessment_id") if isinstance(created, dict) else None
    out: dict = {
        "level": level,
        "create": {"http": code, "assessment_id": aid, "workflow_id": created.get("workflow_id")},
    }
    print("create", out["create"])
    if code not in (200, 201) or not aid:
        out["ok"] = False
        out["fail"] = "create_failed"
        return out

    deadline = time.time() + timeout_s
    last: dict = {}
    while time.time() < deadline:
        code, row = call(op, "GET", f"/api/v1/assessments/{aid}")
        last = row if isinstance(row, dict) else {}
        state = last.get("state")
        llm = (last.get("summary") or {}).get("llm_used")
        print(f"  poll state={state} llm_used={llm}")
        if state in ("AWAITING_REVIEW", "COMPLETED", "FAILED", "REJECTED", "CANCELLED"):
            break
        time.sleep(5)
    else:
        out["ok"] = False
        out["fail"] = "timeout"
        out["assessment"] = {"state": last.get("state")}
        return out

    summary = last.get("summary") or {}
    gates = summary.get("domain_gates") or last.get("domain_gates") or {}
    out["assessment"] = {
        "state": last.get("state"),
        "headline": summary.get("headline"),
        "recommendation": summary.get("recommendation"),
        "llm_used": summary.get("llm_used"),
        "domain_gates": gates,
        "gates_count": len(gates),
    }
    print(
        "  result",
        out["assessment"]["state"],
        out["assessment"]["recommendation"],
        "gates",
        len(gates),
        "llm",
        out["assessment"]["llm_used"],
    )

    code, claims = call(op, "GET", f"/api/v1/assessments/{aid}/claims?limit=100")
    items = claims.get("items") if isinstance(claims, dict) else []
    real = [
        c
        for c in items
        if any(
            isinstance(u, str) and u.startswith("http") and "example.com" not in u
            for u in (c.get("source_urls") or [])
        )
    ]
    lineage = [
        c
        for c in items
        if c.get("snapshot_ids") and c.get("evidence_span_ids") and c.get("source_urls") is not None
    ]
    out["claims"] = {
        "total": claims.get("total") if isinstance(claims, dict) else len(items),
        "with_lineage": len(lineage),
        "real_sources": len(real),
    }
    code, contras = call(op, "GET", f"/api/v1/assessments/{aid}/contradictions?limit=50")
    citems = contras.get("items") if isinstance(contras, dict) else []
    out["contradictions"] = {
        "total": contras.get("total") if isinstance(contras, dict) else len(citems),
        "open": sum(1 for c in citems if c.get("resolution") == "open"),
    }

    web_paths = {
        f"/companies/a/{aid}": None,
        f"/companies/a/{aid}?tab=domains": None,
        f"/companies/a/{aid}?tab=sources": None,
    }
    for path in list(web_paths):
        try:
            req = urllib.request.Request(f"{WEB}{path}")
            with urllib.request.urlopen(req, timeout=30) as res:
                web_paths[path] = res.status
        except Exception as exc:  # noqa: BLE001
            web_paths[path] = str(exc)
    out["web"] = web_paths

    min_claims = 5 if level == 1 else 8
    min_gates = 5 if level == 1 else 10
    out["ok"] = (
        out["assessment"]["state"] == "AWAITING_REVIEW"
        and bool(out["assessment"]["llm_used"])
        and out["claims"]["total"] >= min_claims
        and out["claims"]["with_lineage"] >= min_claims
        and out["claims"]["real_sources"] >= 3
        and out["assessment"]["gates_count"] >= min_gates
        and all(v == 200 for v in web_paths.values())
    )
    if not out["ok"]:
        out["fail"] = "assertions"
    out["ui"] = f"{WEB}/companies/a/{aid}"
    print("  ok" if out["ok"] else "  FAIL", out.get("fail"), "claims", out["claims"], "ui", out["ui"])
    return out


def run_level3(op) -> dict:
    print(f"\n=== Level 3 · {COMPANY} (private shell) ===")
    # Screening must stay fail-closed.
    code_block, blocked = call(
        op,
        "POST",
        "/api/v1/assessments",
        {"company_name": COMPANY, "level": 3, "start_screening": True},
    )
    out: dict = {
        "level": 3,
        "screening_blocked": {
            "http": code_block,
            "detail": blocked.get("detail") if isinstance(blocked, dict) else blocked,
            "ok": code_block == 409
            and (blocked.get("detail") if isinstance(blocked, dict) else None)
            == "LEVEL3_PRIVATE_PIPELINE_NOT_READY",
        },
    }
    print("  screening_blocked", out["screening_blocked"])

    code, created = call(
        op,
        "POST",
        "/api/v1/assessments",
        {"company_name": COMPANY, "level": 3, "start_screening": False},
    )
    aid = created.get("assessment_id") if isinstance(created, dict) else None
    out["create"] = {
        "http": code,
        "assessment_id": aid,
        "data_room_id": created.get("data_room_id") if isinstance(created, dict) else None,
        "upload_enabled": created.get("upload_enabled") if isinstance(created, dict) else None,
    }
    print("  create", out["create"])
    if code not in (200, 201) or not aid:
        out["ok"] = False
        out["fail"] = "l3_create_failed"
        return out

    code, room = call(op, "GET", f"/api/v1/assessments/{aid}/data-room")
    out["data_room"] = {"http": code, **(room if isinstance(room, dict) else {})}

    upload_result = None
    if FIXTURE_PDF.is_file() and out["create"].get("upload_enabled"):
        code_u, body_u = upload(op, aid, FIXTURE_PDF)
        upload_result = {"http": code_u, "body": body_u}
        if code_u in (200, 201) and isinstance(body_u, dict) and body_u.get("document_id"):
            doc_id = body_u["document_id"]
            # Wait briefly for q.docs parse
            for _ in range(20):
                time.sleep(2)
                code_d, docs = call(op, "GET", f"/api/v1/assessments/{aid}/documents")
                items = docs.get("items") if isinstance(docs, dict) else []
                row = next((d for d in items if d.get("document_id") == doc_id), None)
                if row and row.get("status") in ("ready", "parse_failed", "quarantined"):
                    upload_result["final"] = row
                    break
            else:
                upload_result["final"] = {"status": "timeout_parsing"}
        print("  upload", upload_result.get("http"), (upload_result.get("final") or {}).get("status"))
    else:
        print("  upload skipped (scanner unavailable or fixture missing)")
    out["upload"] = upload_result

    try:
        req = urllib.request.Request(f"{WEB}/companies/a/{aid}?tab=dataroom")
        with urllib.request.urlopen(req, timeout=30) as res:
            web_code = res.status
    except Exception as exc:  # noqa: BLE001
        web_code = str(exc)
    out["web"] = {f"/companies/a/{aid}?tab=dataroom": web_code}
    out["ui"] = f"{WEB}/companies/a/{aid}?tab=dataroom"

    out["ok"] = bool(
        out["screening_blocked"]["ok"]
        and out["create"]["http"] in (200, 201)
        and out["data_room"].get("exists") is True
        and web_code == 200
        and (
            upload_result is None
            or (
                upload_result.get("http") in (200, 201)
                and (upload_result.get("final") or {}).get("status") in ("ready", "parsing")
            )
            or upload_result.get("http") == 503  # SCANNER_UNAVAILABLE is honest
        )
    )
    if not out["ok"]:
        out["fail"] = "l3_assertions"
    print("  ok" if out["ok"] else "  FAIL", out.get("fail"), "ui", out["ui"])
    return out


def main() -> int:
    report: dict = {"company": COMPANY, "api": API, "web": WEB, "levels": {}}
    print(f"e2e all-levels company={COMPANY} api={API}")
    op = opener()

    code, status = call(op, "GET", "/api/v1/system/status")
    report["status"] = {
        "http": code,
        "mode": status.get("mode") if isinstance(status, dict) else None,
        "provider": (status.get("provider") or {}).get("state") if isinstance(status, dict) else None,
        "model": (status.get("provider") or {}).get("model") if isinstance(status, dict) else None,
        "private_pipeline": status.get("private_pipeline") if isinstance(status, dict) else None,
    }
    print("status", {k: report["status"][k] for k in ("mode", "provider", "model")})
    if code != 200 or report["status"]["provider"] == "missing_key":
        print("FAIL provider / status")
        OUT.write_text(json.dumps(report, indent=2))
        return 1

    code, _ = call(op, "POST", "/api/v1/auth/demo-session")
    if code not in (200, 201):
        print("FAIL demo-session", code)
        return 1

    report["levels"]["1"] = run_public_level(op, 1, timeout_s=360)
    report["levels"]["2"] = run_public_level(op, 2, timeout_s=720)
    report["levels"]["3"] = run_level3(op)

    report["ok"] = all(report["levels"][k].get("ok") for k in ("1", "2", "3"))
    report["uis"] = {k: report["levels"][k].get("ui") for k in ("1", "2", "3")}
    OUT.write_text(json.dumps(report, indent=2))
    print("\n=== SUMMARY ===")
    for k in ("1", "2", "3"):
        lvl = report["levels"][k]
        print(f"L{k} ok={lvl.get('ok')} fail={lvl.get('fail')} ui={lvl.get('ui')}")
    print("ALL OK" if report["ok"] else "ALL FAIL", "wrote", OUT)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
