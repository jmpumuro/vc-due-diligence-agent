#!/usr/bin/env python3
"""E2E value test: screen several startups, compare claims to published pages.

Stricter than keyword overlap: extracts dollars/years/headcount/user figures
from agent statements and checks whether those concrete facts appear on the
cited public page (and optionally a second official URL).
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
OUT = Path(os.environ.get("VALUE_OUT", "/tmp/thesis_agent_value_report.json"))
COMPANIES = [
    c.strip()
    for c in os.environ.get(
        "VALUE_COMPANIES",
        "SonderMind,Notion,Figma,Canva,Stripe",
    ).split(",")
    if c.strip()
]
TIMEOUT = int(os.environ.get("VALUE_TIMEOUT_S", "360"))

# Prefer shared contract grounding (single source of truth with research path).
try:
    from thesis_contracts.grounding import ground_numeric_statement
except ImportError:  # script run without editable install
    ground_numeric_statement = None  # type: ignore[assignment]


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.chunks: list[str] = []
        self._skip = False

    def handle_starttag(self, tag, attrs):  # noqa: ANN001
        if tag in {"script", "style", "noscript"}:
            self._skip = True

    def handle_endtag(self, tag):  # noqa: BLE001, ANN001
        if tag in {"script", "style", "noscript"}:
            self._skip = False

    def handle_data(self, data):  # noqa: ANN001
        if not self._skip and data and data.strip():
            self.chunks.append(data)


def opener():
    return urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
    )


def call(op, method: str, path: str, data: dict | None = None):
    body = None if data is None else json.dumps(data).encode()
    req = urllib.request.Request(
        f"{API}{path}",
        data=body,
        headers={
            "content-type": "application/json",
            "Idempotency-Key": f"value-{time.time_ns()}",
            "User-Agent": "ThesisValueBot/0.1",
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
            url, headers={"User-Agent": "ThesisValueBot/0.1 (claim audit)"}
        )
        with urllib.request.urlopen(req, timeout=25) as res:
            raw = res.read()
        html = raw.decode("utf-8", errors="replace")
        p = _Text()
        p.feed(html)
        text = re.sub(r"\s+", " ", " ".join(p.chunks)).strip()
        return text, None
    except Exception as exc:  # noqa: BLE001
        return "", str(exc)[:200]


_FACT_RE = re.compile(
    r"""
    (?:\$\s?\d[\d,\.]*(?:\s*(?:million|billion|m|b))?)
    |(?:\d[\d,\.]*\s*(?:million|billion)\s+(?:users|customers|employees|people)?)
    |(?:\b(?:19|20)\d{2}\b)
    |(?:\b\d{2,4}\s*(?:\+\s*)?(?:employees|users|customers|therapists)\b)
    """,
    re.I | re.X,
)


def extract_facts(statement: str) -> list[str]:
    if ground_numeric_statement is not None:
        return list(ground_numeric_statement(statement, "").facts)
    return [m.group(0).strip() for m in _FACT_RE.finditer(statement or "")]


def qualitative_overlap(statement: str, page: str) -> float:
    stop = {
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "from",
        "are",
        "was",
        "has",
        "have",
        "its",
        "company",
        "platform",
        "about",
        "all",
        "built",
    }
    words = {
        w
        for w in re.findall(r"[a-z]{4,}", (statement or "").lower())
        if w not in stop
    }
    if not words or not page:
        return 0.0
    pl = page.lower()
    hits = sum(1 for w in words if w in pl)
    return hits / len(words)


def score_claim(statement: str, page_text: str, *, contested: bool) -> dict:
    if ground_numeric_statement is not None:
        g = ground_numeric_statement(statement, page_text)
        facts = list(g.facts)
        fact_hits = list(g.supported_facts)
        fact_misses = list(g.missing_facts)
        contract_verdict = g.verdict
    else:
        facts = extract_facts(statement)
        fact_hits, fact_misses = [], list(facts)
        contract_verdict = "ungrounded" if facts else "no_numeric_facts"

    q = qualitative_overlap(statement, page_text)
    # Prefer agent-persisted trust when present (API already demoted).
    if contested and "registry" in (statement or "").lower():
        verdict = "process_boilerplate"
        value = "low"
    elif facts and fact_misses and not fact_hits:
        verdict = "numeric_unbacked"
        value = "harmful"
    elif facts and fact_hits and not fact_misses:
        verdict = "numeric_supported"
        value = "high"
    elif facts and fact_hits and fact_misses:
        verdict = "numeric_partial"
        value = "mixed"
    elif q >= 0.4:
        verdict = "qualitative_supported"
        value = "useful"
    elif q >= 0.2:
        verdict = "qualitative_weak"
        value = "low"
    else:
        verdict = "unsupported"
        value = "low"

    return {
        "verdict": verdict,
        "value": value,
        "contract_verdict": contract_verdict,
        "facts": facts,
        "fact_hits": fact_hits,
        "fact_misses": fact_misses,
        "qualitative_overlap": round(q, 3),
        "page_chars": len(page_text),
    }


def wait_assessment(op, aid: str) -> dict:
    deadline = time.time() + TIMEOUT
    last: dict = {}
    while time.time() < deadline:
        _, row = call(op, "GET", f"/api/v1/assessments/{aid}")
        last = row if isinstance(row, dict) else {}
        state = last.get("state")
        print(f"  poll {aid[:8]}… {state}")
        if state in (
            "AWAITING_REVIEW",
            "COMPLETED",
            "FAILED",
            "REJECTED",
            "INFORMATION_REQUESTED",
        ):
            return last
        time.sleep(5)
    last["_timeout"] = True
    return last


def run_company(op, name: str) -> dict:
    print(f"\n=== {name} ===")
    code, created = call(
        op,
        "POST",
        "/api/v1/assessments",
        {"company_name": name, "level": 1, "start_screening": True},
    )
    aid = created.get("assessment_id") if isinstance(created, dict) else None
    out: dict = {"company": name, "create_http": code, "assessment_id": aid}
    if code not in (200, 201) or not aid:
        out["ok"] = False
        out["fail"] = "create"
        return out

    row = wait_assessment(op, aid)
    summary = row.get("summary") or {}
    out.update(
        {
            "state": row.get("state"),
            "headline": summary.get("headline"),
            "recommendation": summary.get("recommendation"),
            "llm_used": summary.get("llm_used"),
            "domain_gates": summary.get("domain_gates") or {},
        }
    )

    _, claims_body = call(op, "GET", f"/api/v1/assessments/{aid}/claims?limit=50")
    items = (claims_body or {}).get("items") if isinstance(claims_body, dict) else []
    page_cache: dict[str, str] = {}
    comparisons = []
    for c in items:
        urls = [
            u
            for u in (c.get("source_urls") or [])
            if isinstance(u, str) and u.startswith("http") and "example.com" not in u
            and not str(u).endswith("/mirror")
        ]
        url = urls[0] if urls else None
        page = ""
        err = None
        if url:
            if url not in page_cache:
                page_cache[url], err = fetch_text(url)
            page = page_cache[url]
        check = score_claim(
            str(c.get("statement") or ""),
            page,
            contested=c.get("trust_state") == "contested",
        )
        if err:
            check["fetch_error"] = err
        check["checked_url"] = url
        comparisons.append(
            {
                "domain_id": c.get("domain_id"),
                "trust_state": c.get("trust_state"),
                "statement": c.get("statement"),
                "check": check,
            }
        )
        print(
            f"  [{c.get('domain_id')}] {check['verdict']} value={check['value']} "
            f"facts_miss={check['fact_misses'][:2]}"
        )

    tallies: dict[str, int] = {}
    value_tallies: dict[str, int] = {}
    for e in comparisons:
        ch = e["check"]
        tallies[ch["verdict"]] = tallies.get(ch["verdict"], 0) + 1
        value_tallies[ch["value"]] = value_tallies.get(ch["value"], 0) + 1

    # Value score: useful/high minus harmful
    score = (
        value_tallies.get("high", 0) * 2
        + value_tallies.get("useful", 0)
        + value_tallies.get("mixed", 0) * 0.5
        - value_tallies.get("harmful", 0) * 2
        - value_tallies.get("low", 0) * 0.25
    )
    out["comparisons"] = comparisons
    out["verdict_tallies"] = tallies
    out["value_tallies"] = value_tallies
    out["value_score"] = round(score, 2)
    out["unique_sources"] = sorted({c["check"].get("checked_url") for c in comparisons if c["check"].get("checked_url")})
    out["ok"] = out.get("state") in ("AWAITING_REVIEW", "COMPLETED") and bool(out.get("llm_used"))
    return out


def main() -> int:
    print(f"value test companies={COMPANIES} api={API}")
    op = opener()
    code, status = call(op, "GET", "/api/v1/system/status")
    if code != 200 or status.get("mode") not in ("live_ready", "degraded"):
        print("FAIL status", code, status.get("mode") if isinstance(status, dict) else None)
        return 1
    print(
        "mode",
        status.get("mode"),
        "search",
        (status.get("search") or {}).get("state"),
        "provider",
        (status.get("provider") or {}).get("state"),
    )
    code, _ = call(op, "POST", "/api/v1/auth/demo-session")
    if code not in (200, 201):
        print("FAIL demo-session")
        return 1

    results = [run_company(op, name) for name in COMPANIES]
    harmful = sum((r.get("value_tallies") or {}).get("harmful", 0) for r in results)
    useful = sum(
        (r.get("value_tallies") or {}).get("useful", 0)
        + (r.get("value_tallies") or {}).get("high", 0)
        for r in results
    )
    report = {
        "api": API,
        "search_state": (status.get("search") or {}).get("state"),
        "companies": COMPANIES,
        "results": results,
        "portfolio": {
            "companies_ok": sum(1 for r in results if r.get("ok")),
            "companies_total": len(results),
            "useful_or_high_claims": useful,
            "harmful_numeric_claims": harmful,
            "avg_value_score": round(
                sum(r.get("value_score") or 0 for r in results) / max(1, len(results)), 2
            ),
            "judgment": (
                "net_positive_with_caveats"
                if useful > harmful and harmful < useful
                else "mixed_or_negative_while_search_degraded"
            ),
        },
        "summary": [
            {
                "company": r.get("company"),
                "state": r.get("state"),
                "recommendation": r.get("recommendation"),
                "value_score": r.get("value_score"),
                "value_tallies": r.get("value_tallies"),
                "verdict_tallies": r.get("verdict_tallies"),
                "unique_sources": r.get("unique_sources"),
                "assessment_id": r.get("assessment_id"),
                "ok": r.get("ok"),
            }
            for r in results
        ],
    }
    OUT.write_text(json.dumps(report, indent=2))
    print("\n=== PORTFOLIO VALUE ===")
    print(json.dumps(report["portfolio"], indent=2))
    for s in report["summary"]:
        print(
            f"- {s['company']}: score={s['value_score']} "
            f"tallies={s['value_tallies']} sources={len(s.get('unique_sources') or [])} "
            f"rec={s['recommendation']}"
        )
        if s.get("assessment_id"):
            print(f"  http://localhost:3000/companies/a/{s['assessment_id']}")
    print("wrote", OUT)
    return 0 if report["portfolio"]["companies_ok"] == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
