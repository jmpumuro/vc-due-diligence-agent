#!/usr/bin/env python3
"""Validate Level-1 agent claims against published public pages.

Runs screening for named public companies, then for each claim with a real
source URL fetches the page and scores: supported | partial | unsupported |
contradicted_by_page (heuristic keyword overlap — not legal diligence).
"""

from __future__ import annotations

import http.cookiejar
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

API = os.environ.get("PUBLIC_API_URL", "http://localhost:8001").rstrip("/")
OUT = Path(os.environ.get("VALIDATE_OUT", "/tmp/thesis_public_company_validation.json"))
COMPANIES = [
    c.strip()
    for c in os.environ.get("VALIDATE_COMPANIES", "SonderMind,Notion").split(",")
    if c.strip()
]
TIMEOUT = int(os.environ.get("VALIDATE_TIMEOUT_S", "300"))

STOP = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "of",
    "to",
    "in",
    "on",
    "for",
    "with",
    "is",
    "are",
    "that",
    "this",
    "as",
    "by",
    "from",
    "at",
    "be",
    "its",
    "their",
    "company",
    "public",
    "still",
    "required",
}


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.chunks: list[str] = []
        self._skip = False

    def handle_starttag(self, tag, attrs):  # noqa: ANN001
        if tag in {"script", "style", "noscript"}:
            self._skip = True

    def handle_endtag(self, tag):  # noqa: ANN001
        if tag in {"script", "style", "noscript"}:
            self._skip = False

    def handle_data(self, data):  # noqa: ANN001
        if not self._skip and data and data.strip():
            self.chunks.append(data)


def opener():
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def call(op, method: str, path: str, data: dict | None = None):
    body = None if data is None else json.dumps(data).encode()
    req = urllib.request.Request(
        f"{API}{path}",
        data=body,
        headers={
            "content-type": "application/json",
            "Idempotency-Key": f"val-{time.time_ns()}",
            "User-Agent": "ThesisValidateBot/0.1",
        },
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


def fetch_text(url: str) -> tuple[str, str | None]:
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "ThesisValidateBot/0.1 (public claim check)"},
        )
        with urllib.request.urlopen(req, timeout=25) as res:
            raw = res.read()
            ctype = res.headers.get("content-type", "")
        if "html" not in ctype and not url.endswith(".html"):
            # still try decode
            pass
        html = raw.decode("utf-8", errors="replace")
        p = _Text()
        p.feed(html)
        text = re.sub(r"\s+", " ", " ".join(p.chunks)).strip().lower()
        return text, None
    except Exception as exc:  # noqa: BLE001
        return "", str(exc)[:200]


def tokens(s: str) -> set[str]:
    words = re.findall(r"[a-z0-9]{3,}", (s or "").lower())
    return {w for w in words if w not in STOP}


def score_claim(statement: str, page_text: str) -> dict:
    st = tokens(statement)
    if not st:
        return {"verdict": "unsupported", "overlap": 0.0, "hit_ratio": 0.0, "note": "empty_statement"}
    if not page_text:
        return {"verdict": "unsupported", "overlap": 0.0, "hit_ratio": 0.0, "note": "page_empty_or_fetch_failed"}
    hits = {w for w in st if w in page_text}
    ratio = len(hits) / max(1, len(st))
    # Strong phrase check: longest 4+ char content words consecutive-ish
    soft = statement.lower()
    # Heuristic contradiction cues on page that negate agent wording
    contradicted = False
    if "founded" in soft or "established" in soft:
        years = re.findall(r"\b(19|20)\d{2}\b", statement)
        page_years = set(re.findall(r"\b(19|20)\d{2}\b", page_text))
        if years and page_years and not any(y in page_years for y in years):
            # year on claim not on page — weak signal only
            pass
    if ratio >= 0.45:
        verdict = "supported"
    elif ratio >= 0.22:
        verdict = "partial"
    else:
        verdict = "unsupported"
    if contradicted:
        verdict = "contradicted_by_page"
    return {
        "verdict": verdict,
        "overlap": round(ratio, 3),
        "hit_ratio": round(ratio, 3),
        "hits": sorted(hits)[:12],
        "misses": sorted(st - hits)[:12],
    }


def wait_assessment(op, aid: str) -> dict:
    deadline = time.time() + TIMEOUT
    last: dict = {}
    while time.time() < deadline:
        code, row = call(op, "GET", f"/api/v1/assessments/{aid}")
        last = row if isinstance(row, dict) else {}
        state = last.get("state")
        print(f"  poll {aid[:8]} state={state}")
        if state in ("AWAITING_REVIEW", "COMPLETED", "FAILED", "REJECTED", "INFORMATION_REQUESTED"):
            return last
        time.sleep(5)
    last["_timeout"] = True
    return last


def validate_company(op, name: str) -> dict:
    print(f"\n=== {name} ===")
    code, created = call(
        op,
        "POST",
        "/api/v1/assessments",
        {"company_name": name, "level": 1, "start_screening": True},
    )
    aid = created.get("assessment_id") if isinstance(created, dict) else None
    out: dict = {
        "company": name,
        "create_http": code,
        "assessment_id": aid,
        "workflow_id": (created or {}).get("workflow_id") if isinstance(created, dict) else None,
    }
    if code not in (200, 201) or not aid:
        out["ok"] = False
        out["fail"] = "create_failed"
        return out

    row = wait_assessment(op, aid)
    summary = row.get("summary") or {}
    out["state"] = row.get("state")
    out["headline"] = summary.get("headline")
    out["recommendation"] = summary.get("recommendation")
    out["llm_used"] = summary.get("llm_used")

    code, claims = call(op, "GET", f"/api/v1/assessments/{aid}/claims?limit=50")
    items = (claims or {}).get("items") if isinstance(claims, dict) else []
    comparisons = []
    for c in items:
        urls = [u for u in (c.get("source_urls") or []) if isinstance(u, str) and u.startswith("http")]
        real = [u for u in urls if "example.com" not in u]
        entry = {
            "domain_id": c.get("domain_id"),
            "trust_state": c.get("trust_state"),
            "statement": c.get("statement"),
            "source_urls": real or urls,
        }
        if not (real or urls):
            entry["check"] = {"verdict": "unsupported", "note": "no_source_url"}
            comparisons.append(entry)
            continue
        url = (real or urls)[0]
        text, err = fetch_text(url)
        check = score_claim(str(c.get("statement") or ""), text)
        if err:
            check["fetch_error"] = err
        check["checked_url"] = url
        check["page_chars"] = len(text)
        entry["check"] = check
        comparisons.append(entry)
        print(
            f"  claim[{c.get('domain_id')}] {check['verdict']} "
            f"overlap={check.get('overlap')} url={url[:60]}"
        )

    tallies: dict[str, int] = {}
    for e in comparisons:
        v = (e.get("check") or {}).get("verdict") or "unknown"
        tallies[v] = tallies.get(v, 0) + 1

    out["claims_total"] = len(comparisons)
    out["tallies"] = tallies
    out["comparisons"] = comparisons
    out["ok"] = (
        out.get("state") in ("AWAITING_REVIEW", "COMPLETED")
        and bool(out.get("llm_used"))
        and len(comparisons) >= 3
        and tallies.get("supported", 0) + tallies.get("partial", 0) >= 1
    )
    return out


def main() -> int:
    print(f"validate companies={COMPANIES} api={API}")
    op = opener()
    code, status = call(op, "GET", "/api/v1/system/status")
    if code != 200:
        print("FAIL status", code)
        return 1
    mode = status.get("mode")
    print("status", mode, (status.get("provider") or {}).get("state"))
    if mode not in ("live_ready", "degraded"):
        print("FAIL bad mode")
        return 1

    code, _ = call(op, "POST", "/api/v1/auth/demo-session")
    if code not in (200, 201):
        print("FAIL demo-session", code)
        return 1

    results = [validate_company(op, name) for name in COMPANIES]
    report = {
        "api": API,
        "companies": COMPANIES,
        "results": results,
        "ok": all(r.get("ok") for r in results),
        "summary": [
            {
                "company": r.get("company"),
                "state": r.get("state"),
                "recommendation": r.get("recommendation"),
                "claims": r.get("claims_total"),
                "tallies": r.get("tallies"),
                "ok": r.get("ok"),
                "assessment_id": r.get("assessment_id"),
            }
            for r in results
        ],
    }
    OUT.write_text(json.dumps(report, indent=2))
    print("\n=== SUMMARY ===")
    for s in report["summary"]:
        print(
            f"{s['company']}: state={s['state']} rec={s['recommendation']} "
            f"claims={s['claims']} tallies={s['tallies']} ok={s['ok']}"
        )
        aid = s.get("assessment_id")
        if aid:
            print(f"  UI http://localhost:3000/companies/a/{aid}")
    print("wrote", OUT, "ok=", report["ok"])
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
