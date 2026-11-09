#!/usr/bin/env python3
"""Live smoke: system status + create L1 assessment with OpenAI-backed screening.

Requires a running stack (API on PUBLIC_API_URL) and OPENAI_API_KEY in the API env.
Does not print the API key.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API = os.environ.get("PUBLIC_API_URL", "http://localhost:8001").rstrip("/")


def call(method: str, path: str, *, data: dict | None = None, cookie: str | None = None) -> tuple[int, dict | list | str]:
    headers = {"content-type": "application/json"}
    if cookie:
        headers["cookie"] = cookie
    body = None if data is None else json.dumps(data).encode()
    req = urllib.request.Request(f"{API}{path}", data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as res:
            raw = res.read().decode()
            cookie_out = res.headers.get("Set-Cookie")
            payload: dict | list | str
            try:
                payload = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                payload = raw
            if cookie_out and isinstance(payload, dict):
                payload = {**payload, "_set_cookie": cookie_out.split(";", 1)[0]}
            return res.status, payload
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw


def main() -> int:
    print(f"api={API}")
    code, status = call("GET", "/api/v1/system/status")
    if code != 200 or not isinstance(status, dict):
        print("FAIL status", code, status)
        return 1
    print(
        "status",
        status.get("mode"),
        "provider",
        (status.get("provider") or {}).get("state"),
        "model",
        (status.get("provider") or {}).get("model"),
        "models_sample",
        len((status.get("provider") or {}).get("models") or []),
    )
    if status.get("mode") not in ("live_ready", "degraded"):
        print("FAIL expected live_ready/degraded with OpenAI key")
        return 1
    if (status.get("provider") or {}).get("state") == "missing_key":
        print("FAIL provider missing_key — set OPENAI_API_KEY on API")
        return 1

    code, sess = call("POST", "/api/v1/auth/demo-session")
    if code not in (200, 201) or not isinstance(sess, dict):
        print("FAIL demo-session", code, sess)
        return 1
    # demo-session sets cookie; use jar via header from a manual cookie if returned
    # Fallback: hit with urllib cookie processor
    import http.cookiejar

    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    def call2(method: str, path: str, data: dict | None = None):
        body = None if data is None else json.dumps(data).encode()
        req = urllib.request.Request(
            f"{API}{path}",
            data=body,
            headers={"content-type": "application/json"},
            method=method,
        )
        with opener.open(req, timeout=60) as res:
            return res.status, json.loads(res.read().decode() or "{}")

    call2("POST", "/api/v1/auth/demo-session")
    company = f"OpenAI Smoke Co {int(time.time())}"
    code, created = call2(
        "POST",
        "/api/v1/assessments",
        {"company_name": company, "level": 1, "start_screening": True},
    )
    print("create", code, {k: created.get(k) for k in ("assessment_id", "workflow_id", "state", "detail")})
    if code not in (200, 201):
        return 1
    aid = created["assessment_id"]
    # Poll until AWAITING_REVIEW or timeout
    deadline = time.time() + 240
    last = {}
    while time.time() < deadline:
        code, row = call2("GET", f"/api/v1/assessments/{aid}")
        last = row if isinstance(row, dict) else {}
        state = last.get("state")
        llm = (last.get("summary") or {}).get("llm_used")
        print(f"poll state={state} llm_used={llm}")
        if state in ("AWAITING_REVIEW", "COMPLETED", "FAILED", "REJECTED"):
            break
        time.sleep(4)
    else:
        print("FAIL timeout waiting for screening")
        return 1

    summary = last.get("summary") or {}
    headline = summary.get("headline") or ""
    llm_used = summary.get("llm_used")
    print("headline:", headline[:160])
    print("recommendation:", summary.get("recommendation"))
    print("llm_used:", llm_used)
    if state != "AWAITING_REVIEW":
        print("FAIL expected AWAITING_REVIEW got", state)
        return 1
    if not llm_used:
        print("WARN screening finished but llm_used is false — check worker logs / key in worker env")
    out = {
        "assessment_id": aid,
        "state": state,
        "llm_used": llm_used,
        "headline": headline,
        "mode": status.get("mode"),
    }
    Path("/tmp/thesis_openai_smoke.json").write_text(json.dumps(out, indent=2))
    print("OK wrote /tmp/thesis_openai_smoke.json")
    return 0 if llm_used else 2


if __name__ == "__main__":
    sys.exit(main())
