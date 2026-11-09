#!/usr/bin/env python3
"""Final live E2E: Level 1 screening for SonderMind through memo/review gates.

Exercises demo-session → create assessment → Temporal screening → claims with
snapshot/span lineage → company contradiction → resolve with expected_version →
dashboard/UI-readable assessment summary.

Requires running stack + OPENAI_API_KEY on API/worker. Never invents a D6 URL.
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
COMPANY = os.environ.get("E2E_COMPANY", "SonderMind")
OUT = Path(os.environ.get("E2E_OUT", "/tmp/thesis_e2e_sondermind.json"))


def opener():
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def call(op, method: str, path: str, data: dict | None = None, base: str = API):
    body = None if data is None else json.dumps(data).encode()
    req = urllib.request.Request(
        f"{base}{path}",
        data=body,
        headers={"content-type": "application/json", "Idempotency-Key": f"e2e-{time.time_ns()}"},
        method=method,
    )
    try:
        with op.open(req, timeout=90) as res:
            raw = res.read().decode()
            return res.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"raw": raw}


def main() -> int:
    report: dict = {"company": COMPANY, "api": API, "web": WEB, "steps": []}
    print(f"e2e company={COMPANY} api={API}")
    op = opener()

    code, status = call(op, "GET", "/api/v1/system/status")
    report["status"] = {
        "http": code,
        "mode": status.get("mode") if isinstance(status, dict) else None,
        "provider": (status.get("provider") or {}).get("state") if isinstance(status, dict) else None,
        "model": (status.get("provider") or {}).get("model") if isinstance(status, dict) else None,
    }
    print("status", report["status"])
    if code != 200 or report["status"]["mode"] not in ("live_ready", "degraded"):
        print("FAIL system status")
        OUT.write_text(json.dumps(report, indent=2))
        return 1
    if report["status"]["provider"] == "missing_key":
        print("FAIL missing OpenAI key")
        OUT.write_text(json.dumps(report, indent=2))
        return 1

    code, _ = call(op, "POST", "/api/v1/auth/demo-session")
    report["steps"].append({"demo_session": code})
    if code not in (200, 201):
        print("FAIL demo-session", code)
        OUT.write_text(json.dumps(report, indent=2))
        return 1

    code, created = call(
        op,
        "POST",
        "/api/v1/assessments",
        {"company_name": COMPANY, "level": 1, "start_screening": True},
    )
    aid = created.get("assessment_id") if isinstance(created, dict) else None
    report["create"] = {"http": code, "assessment_id": aid, "workflow_id": created.get("workflow_id")}
    print("create", report["create"])
    if code not in (200, 201) or not aid:
        OUT.write_text(json.dumps(report, indent=2))
        return 1

    deadline = time.time() + 300
    last: dict = {}
    while time.time() < deadline:
        code, row = call(op, "GET", f"/api/v1/assessments/{aid}")
        last = row if isinstance(row, dict) else {}
        state = last.get("state")
        llm = (last.get("summary") or {}).get("llm_used")
        print(f"poll state={state} llm_used={llm}")
        if state in ("AWAITING_REVIEW", "COMPLETED", "FAILED", "REJECTED"):
            break
        time.sleep(4)
    else:
        report["fail"] = "timeout"
        OUT.write_text(json.dumps(report, indent=2))
        print("FAIL timeout")
        return 1

    summary = last.get("summary") or {}
    report["assessment"] = {
        "state": last.get("state"),
        "revision": last.get("revision"),
        "headline": summary.get("headline"),
        "recommendation": summary.get("recommendation"),
        "llm_used": summary.get("llm_used"),
        "domain_gates": summary.get("domain_gates") or last.get("domain_gates"),
    }
    print("headline:", (summary.get("headline") or "")[:180])
    print("recommendation:", summary.get("recommendation"), "llm_used:", summary.get("llm_used"))

    if last.get("state") != "AWAITING_REVIEW":
        report["fail"] = f"state={last.get('state')}"
        OUT.write_text(json.dumps(report, indent=2))
        print("FAIL expected AWAITING_REVIEW")
        return 1

    code, claims = call(op, "GET", f"/api/v1/assessments/{aid}/claims?limit=50")
    items = claims.get("items") if isinstance(claims, dict) else []
    with_lineage = [
        c
        for c in items
        if c.get("snapshot_ids") and c.get("evidence_span_ids") and c.get("source_urls") is not None
    ]
    real_sources = [
        c
        for c in items
        if any(
            isinstance(u, str) and u.startswith("http") and "example.com" not in u
            for u in (c.get("source_urls") or [])
        )
    ]
    report["claims"] = {
        "http": code,
        "total": claims.get("total") if isinstance(claims, dict) else 0,
        "with_lineage": len(with_lineage),
        "real_sources": len(real_sources),
        "sample": [
            {
                "domain_id": c.get("domain_id"),
                "trust_state": c.get("trust_state"),
                "snapshots": len(c.get("snapshot_ids") or []),
                "spans": len(c.get("evidence_span_ids") or []),
                "urls": c.get("source_urls"),
                "statement": (c.get("statement") or "")[:120],
            }
            for c in items[:4]
        ],
    }
    print(
        "claims",
        report["claims"]["total"],
        "lineage",
        report["claims"]["with_lineage"],
        "real_sources",
        report["claims"]["real_sources"],
    )

    code, contras = call(op, "GET", f"/api/v1/assessments/{aid}/contradictions?limit=20")
    citems = contras.get("items") if isinstance(contras, dict) else []
    report["contradictions"] = {
        "http": code,
        "total": contras.get("total") if isinstance(contras, dict) else 0,
        "open": sum(1 for c in citems if c.get("resolution") == "open"),
    }
    print("contradictions", report["contradictions"])

    resolve_ok = None
    stale_409 = None
    if citems:
        c0 = citems[0]
        cid = c0["contradiction_id"]
        ver = int(c0.get("version") or 1)
        code, resolved = call(
            op,
            "POST",
            f"/api/v1/contradictions/{cid}/resolve",
            {
                "expected_version": ver,
                "resolution": "accepted_risk",
                "comment": "SonderMind E2E accept risk",
                "human_review_state": "decided",
            },
        )
        resolve_ok = code == 200 and resolved.get("resolution") == "accepted_risk"
        code2, stale = call(
            op,
            "POST",
            f"/api/v1/contradictions/{cid}/resolve",
            {"expected_version": ver, "resolution": "waived"},
        )
        stale_409 = code2 == 409
        report["resolve"] = {
            "http": code,
            "ok": resolve_ok,
            "version": resolved.get("version") if isinstance(resolved, dict) else None,
            "stale_409": stale_409,
            "stale_body": stale if isinstance(stale, dict) else None,
        }
        print("resolve", report["resolve"])

    # Progress SSE snapshot (durable events)
    code, prog = call(op, "GET", f"/api/v1/assessments/{aid}/progress?limit=50")
    pev = (prog.get("events") or prog.get("items") or []) if isinstance(prog, dict) else []
    report["progress"] = {
        "http": code,
        "events": len(pev),
        "completed_domains": (prog.get("summary") or {}).get("completed_domains")
        if isinstance(prog, dict)
        else [],
        "summary_keys": sorted((prog.get("summary") or {}).keys()) if isinstance(prog, dict) else [],
    }
    print("progress", report["progress"])

    # UI pages must render
    web_ok = {}
    for path in ("/", f"/companies/a/{aid}", f"/companies/a/{aid}?tab=contradictions", f"/companies/a/{aid}?tab=sources"):
        try:
            req = urllib.request.Request(f"{WEB}{path}")
            with urllib.request.urlopen(req, timeout=30) as res:
                web_ok[path] = res.status
        except urllib.error.HTTPError as e:
            web_ok[path] = e.code
        except Exception as exc:  # noqa: BLE001
            web_ok[path] = str(exc)
    report["web"] = web_ok
    print("web", web_ok)

    gates = report["assessment"].get("domain_gates") or {}
    require_real = os.environ.get("E2E_REQUIRE_REAL_SOURCES", "1") == "1"
    ok = (
        report["assessment"]["state"] == "AWAITING_REVIEW"
        and bool(report["assessment"]["llm_used"])
        and report["claims"]["total"] >= 5
        and report["claims"]["with_lineage"] >= 5
        and report["contradictions"]["total"] >= 1
        and resolve_ok is True
        and stale_409 is True
        and all(v == 200 for v in web_ok.values())
        and (not require_real or report["claims"]["real_sources"] >= 3)
    )
    if require_real and report["claims"]["real_sources"] < 3:
        report["fail"] = "insufficient_real_sources"
    report["ok"] = ok
    report["gates_count"] = len(gates)
    OUT.write_text(json.dumps(report, indent=2))
    print("OK" if ok else "FAIL", "wrote", OUT)
    print(f"UI: {WEB}/companies/a/{aid}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
