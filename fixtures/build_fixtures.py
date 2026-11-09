"""Builds fixtures/dd/*.json in the backend's wire format and validates every file against models.py.

Numbers in calculations.json are computed here from their traced inputs (Decimal), not typed in.
Run:  python3 build_fixtures.py
"""
import hashlib, json, sys
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal as D, ROUND_HALF_UP
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from thesis_contracts import dd as M

OUT = Path(__file__).parent / "dd"
OUT.mkdir(exist_ok=True)
U = lambda name: str(uuid5(NAMESPACE_URL, "thesis-fixture/" + name))
FIRM = "frm_dev"
ASM, ASM_L1 = U("asm/lattice"), U("asm/brightwater")
ANA, PRIYA, MARCO = U("user/ana"), U("user/priya"), U("user/marco")
T0 = datetime(2026, 11, 7, 16, 24, tzinfo=timezone.utc)
iso = lambda dt: dt.isoformat().replace("+00:00", "Z")
def P(s, e, g): return {"start": s, "end": e, "granularity": g}
def q2(x, places="0.0001"): return D(x).quantize(D(places), rounding=ROUND_HALF_UP)
def dump(name, obj): (OUT / name).write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str) + "\n")

company = {"company_id": U("cmp/lattice"), "canonical_name": "Lattice Grid", "primary_domain": "latticegrid.io",
           "aliases": [{"value": "Lattice Grid GmbH", "kind": "name", "source": "commercial register", "confidence": "0.99"}]}

# ---------------- documents ----------------
DOCS = [  # filename, mime, size, status, class, parser, pages, reason, flags, by
    ("Pitch deck Oct 2026.pdf", "application/pdf", 4_812_330, "ready", "pitch_deck", "pypdf@5", 24, None, 1, ANA),
    ("KPI workbook Sep 2026.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 388_120, "needs_validation", "financials", "openpyxl@3", None, None, 0, PRIYA),
    ("Management accounts FY2025.pdf", "application/pdf", 1_120_400, "ready", "financials", "pdfplumber@0.11", 18, None, 0, PRIYA),
    ("Cap table Oct 2026.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 64_200, "ready", "cap_table", "openpyxl@3", None, None, 0, PRIYA),
    ("Customer revenue 2026.csv", "text/csv", 96_513, "ready", "customer_revenue", "csv@py3.12", None, None, 0, PRIYA),
    ("MSA Stadtwerke Nordhafen.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", 210_884, "ready", "contract", "python-docx@1", 31, None, 0, MARCO),
    ("Security policy set.pdf", "application/pdf", 2_004_118, "ready", "policy", "pypdf@5", 42, None, 0, MARCO),
    ("invoice-tool.xlsm", "application/vnd.ms-excel.sheet.macroEnabled.12", 51_002, "rejected", None, None, None, "UNSUPPORTED_FORMAT: macro-enabled files are not accepted", 0, MARCO),
    ("signed_contracts.zip", "application/zip", 7_340_032, "quarantined", None, None, None, "MALWARE_DETECTED: ClamAV signature match", 0, MARCO),
]
documents, doc_id = [], {}
for i, (fn, mime, size, st, cls, parser, pages, reason, flags, by) in enumerate(DOCS):
    did = U("doc/" + fn); doc_id[fn] = did
    documents.append({"document_id": did, "version": 2 if fn.startswith("Pitch") else 1, "assessment_id": ASM, "filename": fn,
        "declared_mime": mime, "detected_mime": None if st == "quarantined" else mime, "size_bytes": size,
        "sha256": hashlib.sha256(fn.encode()).hexdigest(), "status": st, "reject_reason": reason,
        "classification": cls, "classification_source": ("user" if fn.startswith("MSA") else "model") if cls else None,
        "parser": parser, "page_count": pages, "injection_flags": flags, "uploaded_by": by,
        "object_key": f"dataroom/{FIRM}/dr_31/{did}/v1.enc", "key_id": "dk_dr31_01"})

# ---------------- financial table (MRR) ----------------
KPI = doc_id["KPI workbook Sep 2026.xlsx"]
months = [(date(2026, m, 1), date(2026, m, [30, 31, 31, 30][m - 6])) for m in (6, 7, 8, 9)]
cols = "BCDE"
def row(line, vals, raws=None, conf=None, total=False):
    cells = []
    for i, v in enumerate(vals):
        s, e = months[i]
        cells.append({"period": P(s, e, "month"), "value": None if v is None else str(v), "raw": (raws or {}).get(i, f"{v:,}"),
                      "locator": {"kind": "sheet", "sheet": "MRR", "cell": f"{cols[i]}{ {'New MRR':2,'Expansion MRR':3,'Churned MRR':4,'Total MRR':5}[line] }"},
                      "confidence": str((conf or {}).get(i, D("0.98")))})
    r = {"line": line, "cells": cells}
    if total: r.update(is_total=True, total_of=["New MRR", "Expansion MRR", "Churned MRR"], total_rule="rollforward")
    return r
def mrr_table(version, churn_jul, status, corrections, validated_by):
    rows = [row("New MRR", [3900, 4400, 3100, 2100]),
            row("Expansion MRR", [1200, 1050, 1400, 600], conf={3: D("0.71")}),
            row("Churned MRR", [-1800, churn_jul, -900, -2100], raws={1: "4,100" if churn_jul > 0 else "-4,100"}, conf={1: D("0.55") if churn_jul > 0 else D("1")}),
            row("Total MRR", [47800, 49150, 52750, 53350], conf={1: D("0.64") if churn_jul > 0 else D("1")}, total=True)]
    ok = churn_jul < 0
    return {"financial_table_id": U("ftb/mrr"), "version": version, "document_id": KPI, "statement": "kpi", "currency": "EUR",
            "periods": [P(s, e, "month") for s, e in months], "rows": rows,
            "checks": [{"check": "foots", "passed": ok, "detail": None if ok else "Total MRR Jul 2026 ≠ Jun total + movements"},
                       {"check": "contiguous_periods", "passed": True}, {"check": "single_currency", "passed": True},
                       {"check": "sign_convention", "passed": ok, "detail": None if ok else "Churned MRR Jul 2026 positive; other months negative"},
                       {"check": "low_confidence_cells", "passed": ok, "detail": None if ok else "3 cells below 0.75 confidence"}],
            "status": status, "validated_by": validated_by, "corrections": corrections}
table_v1 = mrr_table(1, 4100, "needs_validation", [], None)
table_v2 = mrr_table(2, -4100, "validated", [{"correction_id": U("cor/1"), "author": PRIYA, "line": "Churned MRR", "period_start": "2026-07-01",
    "old_value": "4100", "new_value": "-4100", "reason": "Source sheet shows −4,100; minus sign was read as a hyphen", "at": iso(T0 + timedelta(minutes=9))}], PRIYA)

# ---------------- calculations (computed from inputs) ----------------
def inp(name, value, unit, period, **ref): return {"name": name, "value": str(value), "unit": unit, "period": period, **ref}
MA = doc_id["Management accounts FY2025.pdf"]; CR = doc_id["Customer revenue 2026.csv"]
pm = lambda p: {"kind": "page", "page": p}; sh = lambda s, c: {"kind": "sheet", "sheet": s, "cell": c}
calcs = []
def calc(metric, unit, period, inputs, value=None, status="computed", currency=None, assumptions=(), missing=(), issues=()):
    calcs.append({"calculation_id": U("calc/" + metric), "metric": metric, "formula_version": "ddcalc@1", "status": status,
                  "value": None if value is None else str(value), "unit": unit, "currency": currency, "period": period,
                  "inputs": inputs, "assumptions": list(assumptions), "missing_inputs": list(missing), "validation_issues": list(issues)})
pt = lambda d0: P(d0, d0, "point")
r0, r1 = D(18950), D(53350)
calc("revenue_growth_yoy", "ratio", P("2025-09-01", "2026-09-30", "year"),
     [inp("mrr_start", r0, "EUR/month", P("2025-09-01", "2025-09-30", "month"), document_id=KPI, document_version=1, locator=sh("MRR_history", "N5")),
      inp("mrr_end", r1, "EUR/month", P("2026-09-01", "2026-09-30", "month"), document_id=KPI, document_version=1, locator=sh("MRR", "E5"))],
     q2((r1 - r0) / r0), assumptions=["MRR used as revenue proxy; Total MRR rows are not affected by the unvalidated July cell"])
rev, cogs = D(412000), D(118650)
calc("gross_margin", "ratio", P("2025-01-01", "2025-12-31", "year"),
     [inp("revenue", rev, "EUR", P("2025-01-01", "2025-12-31", "year"), document_id=MA, document_version=1, locator=pm(3)),
      inp("cogs", cogs, "EUR", P("2025-01-01", "2025-12-31", "year"), document_id=MA, document_version=1, locator=pm(3))],
     q2((rev - cogs) / rev), currency=None, assumptions=["Hosting and implementation staff classified as COGS, as stated on p. 3"])
c_start, c_end = D(2594000), D(2240000)
burn = (c_start - c_end) / 3
calc("net_burn_monthly", "EUR/month", P("2026-07-01", "2026-09-30", "quarter"),
     [inp("cash_start", c_start, "EUR", pt("2026-06-30"), document_id=KPI, document_version=1, locator=sh("Cash", "B4")),
      inp("cash_end", c_end, "EUR", pt("2026-09-30"), document_id=KPI, document_version=1, locator=sh("Cash", "E4"))],
     q2(burn, "1"), currency="EUR", assumptions=["No financing inflows in the period (checked against bank summary)"])
calc("runway_months", "months", pt("2026-09-30"),
     [inp("cash_end", c_end, "EUR", pt("2026-09-30"), document_id=MA, document_version=1, locator=pm(4)),
      inp("net_burn_monthly", q2(burn, "1"), "EUR/month", P("2026-07-01", "2026-09-30", "quarter"), claim_id=U("calc/net_burn_monthly"))],
     q2(c_end / q2(burn, "1"), "0.1"), assumptions=["Burn held at the Jul–Sep average"])
arr = 12 * r1
calc("arr_from_mrr", "EUR", pt("2026-09-30"),
     [inp("mrr_end", r1, "EUR/month", P("2026-09-01", "2026-09-30", "month"), document_id=KPI, document_version=1, locator=sh("MRR", "E5"))],
     arr, status="flagged", currency="EUR",
     issues=[f"Deck (Pitch deck Oct 2026.pdf, slide 9) states ARR €900,000; difference {q2((D(900000) - arr) / arr * 100, '0.1')}% exceeds 2% tolerance"])
for m, miss in [("net_revenue_retention", ["validated MRR table ftb (version ≥ 2)"]), ("gross_revenue_retention", ["validated MRR table ftb (version ≥ 2)"]),
                ("cac", ["sales and marketing spend, last 12 months"]), ("ltv", ["customer-level churn history"]), ("cac_payback_months", ["cac"])]:
    calc(m, "ratio" if "retention" in m else "EUR" if m in ("cac", "ltv") else "months", P("2025-10-01", "2026-09-30", "year"), [], None,
         status="not_computable", missing=miss)
top, total = D(239105), D(412250)
calc("top_customer_share", "ratio", P("2026-01-01", "2026-09-30", "quarter"),
     [inp("top_customer_revenue", top, "EUR", P("2026-01-01", "2026-09-30", "quarter"), document_id=CR, document_version=1, locator=sh("Customer revenue 2026", "C2:C1212")),
      inp("total_revenue", total, "EUR", P("2026-01-01", "2026-09-30", "quarter"), document_id=CR, document_version=1, locator=sh("Customer revenue 2026", "C2:C1212"))],
     q2(top / total), assumptions=["Customer IDs merged where the same legal entity appears twice"])
act, bud = D(154250), D(179360)
calc("forecast_vs_actual_q3", "ratio", P("2026-07-01", "2026-09-30", "quarter"),
     [inp("actual", act, "EUR", P("2026-07-01", "2026-09-30", "quarter"), document_id=KPI, document_version=1, locator=sh("Actuals", "D9")),
      inp("budget", bud, "EUR", P("2026-07-01", "2026-09-30", "quarter"), document_id=KPI, document_version=1, locator=sh("Budget 2026", "D9"))],
     q2((act - bud) / bud))

# ---------------- findings (sample of 12 of 76) ----------------
F = {}
def finding(key, domain, kind, stmt, scope="public", conf="high", mat="medium", calc_key=None, basis=()):
    fid = U("fnd/" + key); F[key] = fid
    return {"finding_id": fid, "assessment_id": ASM, "revision": 4, "domain_id": domain, "kind": kind, "statement": stmt,
            "claim_ids": [] if kind in ("derived_calculation", "missing", "inference") else [U("clm/" + key)],
            "calculation_id": U("calc/" + calc_key) if calc_key else None, "based_on_finding_ids": [F[b] for b in basis],
            "claim_confidence": conf, "materiality": mat, "evidence_scope": scope, "access": "workspace" if scope == "public" else "deal_team"}
findings = [
    finding("identity", "company", "verified_fact", "Lattice Grid GmbH is registered in Berlin, incorporated 14 March 2024."),
    finding("founders", "team", "verified_fact", "CEO led grid-operations software at a German utility for eight years.", mat="high"),
    finding("market", "market", "verified_fact", "About 900 electricity distribution operators work in Germany."),
    finding("customers", "traction", "source_supported", "The company lists three municipal utilities as customers; two confirm it publicly.", conf="medium", mat="high"),
    finding("seed", "capitalization", "contradictory", "Seed round reported as €4.2M (company) and €3.5M (news aggregator).", conf="medium"),
    finding("runway", "financials", "derived_calculation", "Runway is 19.0 months at the Jul–Sep 2026 average net burn.", scope="private", mat="high", calc_key="runway_months"),
    finding("arr", "financials", "contradictory", "Deck ARR €900k vs KPI workbook 12 × MRR = €640k.", scope="private", conf="medium", mat="critical"),
    finding("concentration", "traction", "derived_calculation", "Largest customer is 58% of 2026 revenue.", scope="private", mat="high", calc_key="top_customer_share"),
    finding("cac", "financials", "missing", "Customer acquisition cost could not be calculated: sales and marketing spend not provided.", scope="private", conf="low"),
    finding("ip", "legal", "unresolved_risk", "No IP assignment found for code the CTO wrote before incorporation.", scope="private", conf="medium", mat="critical"),
    finding("pentest", "security", "missing", "No penetration test summary in the last 12 months.", scope="private", conf="low"),
    finding("pull_forward", "market", "inference", "The 2027 regulatory deadline is likely to pull purchasing forward.", conf="low", basis=("market",)),
]

# ---------------- domains & measures ----------------
DOM = [  # id, status, gate, reason, found, required, findings, contra, risks, reqs, retry
    ("company", "complete", "sufficient", "Registry record and incorporation documents agree", 6, 4, 7, 0, 0, 0, False),
    ("team", "complete", "sufficient", "Each founder confirmed by an independent source", 8, 6, 7, 0, 0, 0, False),
    ("market", "complete", "partial", "Only one independent market estimate", 3, 4, 5, 0, 0, 0, False),
    ("competition", "complete", "sufficient", "Five competitors, pricing checked", 6, 5, 6, 0, 1, 0, False),
    ("product", "complete", "partial", "Forecast-accuracy claim could not be verified", 5, 6, 7, 0, 0, 0, False),
    ("traction", "complete", "partial", "2 of 3 customers confirmed by the customer", 5, 6, 8, 1, 1, 0, False),
    ("financials", "partial", "partial", "validation_pending: 1 table waiting for validation (does not block the report)", 9, 12, 9, 1, 2, 1, False),
    ("capitalization", "complete", "sufficient", "Cap table reconciles to registry", 5, 4, 5, 1, 0, 0, False),
    ("legal", "complete", "partial", "IP assignment missing for CTO", 7, 9, 7, 0, 1, 1, False),
    ("security", "failed", "insufficient", "search_unavailable: web search was unavailable during the run", 2, 7, 2, 0, 0, 1, True),
    ("governance", "complete", "sufficient", "Board minutes for 4 quarters", 4, 4, 4, 0, 0, 0, False),
    ("thesis_fit", "complete", "sufficient", "Every required criterion answered", 9, 6, 9, 0, 0, 0, False),
]
domains = [dict(zip(["domain_id", "status", "gate_result", "reason", "sources_found", "sources_required", "findings",
                     "contradictions", "risks", "requests", "can_retry"], d)) for d in DOM]
cnt = lambda g: sum(d["gate_result"] == g for d in domains)
measures = {"source_reliability": {"label": "good", "independent_share": "0.62", "company_only_share": "0.38"},
            "claim_confidence": {"label": "medium", "verified": 31, "source_supported": 18, "inference": 4},
            "evidence_coverage": {"domains_sufficient": cnt("sufficient"), "domains_partial": cnt("partial"),
                                  "domains_insufficient": cnt("insufficient"), "domains_not_run": cnt("not_applicable") + cnt("unavailable_at_level")},
            "attractiveness": {"score": "3.8", "range": ["3.2", "4.4"], "advance_threshold": "3.5"}}
finding_counts = {"verified_fact": 31, "source_supported": 18, "derived_calculation": 9, "inference": 4, "contradictory": 3, "missing": 6, "unresolved_risk": 5}
assert sum(finding_counts.values()) == sum(d["findings"] for d in domains), "finding totals disagree with domains"
conditions = ["Resolve the ARR difference between the deck and the KPI workbook",
              "Obtain a signed IP assignment from the CTO covering pre-incorporation work",
              "Reference calls with both confirmed utilities to test concentration risk"]
REPORT_ID = U("rv/4")
scorecard = [{"criterion_id": c, "score": s, "weight": w, "facts_count": n, "evidence_strength": e, "rationale": r,
              "revised_after_critique": rv, "finding_ids": fl}
             for c, s, w, n, e, r, rv, fl in [
                 ("team", 4, "0.25", 7, "strong", "Deep grid-operations experience; prior forecasting product.", False, [F["founders"]]),
                 ("market", 4, "0.20", 4, "good", "Regulation pushes ~900 operators toward forecasting.", False, [F["market"]]),
                 ("product", 4, "0.20", 6, "mixed", "Live at two utilities; accuracy claim unverified.", False, [F["customers"]]),
                 ("traction", 2, "0.20", 8, "weak", "Concentrated revenue; deck ARR not reconciled.", True, [F["concentration"], F["arr"]]),
                 ("thesis_fit", 5, "0.15", 9, "strong", "Climate B2B, Europe, seed, regulated buyers.", False, [F["identity"]])]]
summary = {"assessment_id": ASM, "company": company, "revision": 4, "level": 3, "state": "AWAITING_REVIEW", "stage": None,
           "status_copy_key": "awaiting_review", "recommendation": "advance", "conditions": conditions,
           "headline": "Strong fit with your climate thesis and a proven team. Resolve the ARR difference, the CTO IP assignment and customer concentration before a term sheet.",
           "measures": measures, "domains": domains, "finding_counts": finding_counts, "open_risks": 4, "open_requests": 4,
           "advance_threshold": "3.5", "thesis_fit": "strong", "scorecard": scorecard, "progress": None, "can_decide": True,
           "report_version_id": REPORT_ID}

# Level 1 example (Brightwater Labs): 8 domains run, 4 unavailable_at_level
L1RUN = {"company", "team", "market", "competition", "product", "traction", "capitalization", "thesis_fit"}
l1_domains = []
for d in DOM:
    if d[0] in L1RUN:
        g = "sufficient" if d[0] in ("company", "team", "competition", "capitalization", "thesis_fit", "product") else "partial"
        l1_domains.append({"domain_id": d[0], "status": "complete", "gate_result": g, "reason": "Screening depth · public sources",
                           "sources_found": 2, "sources_required": 2 if g == "sufficient" else 3, "findings": 3, "contradictions": 0,
                           "risks": 0, "requests": 0, "can_retry": False})
    else:
        l1_domains.append({"domain_id": d[0], "status": "skipped", "gate_result": "unavailable_at_level", "reason": "Runs from Level 2",
                           "sources_found": 0, "sources_required": 0, "findings": 0, "contradictions": 0, "risks": 0, "requests": 0, "can_retry": False})
c1 = lambda g: sum(x["gate_result"] == g for x in l1_domains)
summary_l1 = {"assessment_id": ASM_L1, "company": {"company_id": U("cmp/brightwater"), "canonical_name": "Brightwater Labs", "primary_domain": "brightwater.dev", "aliases": []},
              "revision": 1, "level": 1, "state": "AWAITING_REVIEW", "stage": None, "status_copy_key": "awaiting_review",
              "recommendation": "hold", "conditions": [], "headline": "Good fit but early; one public pilot. Level 2 would check legal, security and governance.",
              "measures": {"source_reliability": {"label": "fair", "independent_share": "0.48", "company_only_share": "0.52"},
                           "claim_confidence": {"label": "low", "verified": 11, "source_supported": 7, "inference": 2},
                           "evidence_coverage": {"domains_sufficient": c1("sufficient"), "domains_partial": c1("partial"), "domains_insufficient": c1("insufficient"),
                                                 "domains_not_run": c1("unavailable_at_level") + c1("not_applicable")},
                           "attractiveness": {"score": "3.3", "range": ["2.7", "3.8"], "advance_threshold": "3.5"}},
              "domains": l1_domains, "finding_counts": {"verified_fact": 11, "source_supported": 7, "derived_calculation": 0, "inference": 2, "contradictory": 1, "missing": 2, "unresolved_risk": 1},
              "open_risks": 0, "open_requests": 0, "advance_threshold": "3.5", "thesis_fit": "moderate", "scorecard": [], "progress": None,
              "can_decide": True, "report_version_id": U("rv/bw1")}

# ---------------- report ----------------
S = [  # key, status, reason, body, findings, access
    ("executive_summary", "supported", None, summary["headline"], ["founders", "arr", "ip", "concentration"], "deal_team"),
    ("company_overview", "supported", None, "Lattice Grid GmbH, registered in Berlin in March 2024 [finding:identity], sells load-forecasting software to distribution operators.", ["identity"], "workspace"),
    ("thesis_alignment", "supported", None, "Meets all six required criteria; no exclusion applies.", ["identity", "market"], "workspace"),
    ("business_model", "supported", None, "Annual licences priced per substation; deck pricing matches the public pricing page.", ["customers"], "workspace"),
    ("team", "supported", None, "Both founders' prior roles confirmed by independent sources [finding:founders].", ["founders"], "workspace"),
    ("market", "incomplete", "Only one independent market estimate", "Company model €310M vs one independent estimate €240M; shown as a range, not blended.", ["market", "pull_forward"], "workspace"),
    ("competition", "supported", None, "Five competitors; two well-funded incumbents with overlapping products, both named in the deck.", ["market"], "workspace"),
    ("product_technology", "incomplete", "Forecast-accuracy claim could not be verified", "Live at two utilities with public API documentation.", ["customers"], "workspace"),
    ("traction", "incomplete", "Third customer not confirmed", "Three paying customers; two confirmed publicly. Largest customer 58% of revenue [calc:top_customer_share].", ["customers", "concentration"], "deal_team"),
    ("financial_analysis", "incomplete", "validation_pending: MRR table not yet validated; CAC inputs missing", "ARR €640,200 from 12 × MRR, flagged against the deck's €900k [calc:arr_from_mrr]; runway 19.0 months [calc:runway_months]. CAC, LTV and payback not computable.", ["runway", "arr", "cac"], "deal_team"),
    ("capitalization", "supported", None, "Cap table reconciles to the registry share count; seed amount disputed in public sources.", ["seed"], "deal_team"),
    ("legal_regulatory", "incomplete", "IP assignment missing", "No IP assignment found for pre-incorporation code. No litigation or sanctions matches in public records.", ["ip"], "deal_team"),
    ("security_operational", "incomplete", "search_unavailable: public posture check did not run", "Policies reviewed; no penetration test in the last 12 months.", ["pentest"], "deal_team"),
    ("red_flags", "supported", None, "Concentration, missing CTO IP assignment, deck ARR higher than the workbook.", ["concentration", "ip", "arr"], "deal_team"),
    ("contradictions", "supported", None, "Three open: seed amount, ARR, customer count.", ["seed", "arr"], "deal_team"),
    ("coverage_confidence", "supported", None, "6 of 12 domains sufficient, 5 partial, 1 insufficient. 38% of material findings rest only on company documents.", ["identity"], "workspace"),
    ("missing_information", "supported", None, "Four requests, two blocking a recommendation.", ["cac", "ip", "pentest"], "deal_team"),
    ("scenarios", "supported", None, "Gross multiple on a €2M ticket: bear 0.6×, base 3.1×, bull 8.4×; assumptions labelled.", ["runway"], "deal_team"),
    ("next_actions", "supported", None, "Reference calls; obtain CTO IP assignment; reconcile ARR definition; request a penetration test summary.", [], "deal_team"),
    ("ic_considerations", "supported", None, "Concentration and the IP assignment are suggested conditions for a term sheet. The decision is yours.", [], "deal_team"),
    ("evidence_appendix", "supported", None, "142 saved web sources and 9 documents; every finding links to its saved copy or document page.", ["identity"], "workspace"),
]
assert [s[0] for s in S] == M.SECTION_KEYS
report = {"report_version_id": REPORT_ID, "assessment_id": ASM, "revision": 4, "level": 3, "schema_version": "ddreport@1",
          "evidence_snapshot_set_id": U("ess/104"), "recommendation": "advance", "conditions": conditions, "measures": measures,
          "sections": [{"number": i + 1, "key": k, "status": st, "status_reason": rs, "body_md": b, "finding_ids": [F[x] for x in fl], "access": ac}
                       for i, (k, st, rs, b, fl, ac) in enumerate(S)],
          "disclaimers": ["Sections 10, 12 and 13 identify issues and questions; they are not accounting, legal or security certification.",
                          "Level 3 export: confidential to the deal team."],
          "created_at": iso(T0 - timedelta(minutes=12)), "approved_by": None}

# ---------------- risks, requests ----------------
risks = [{"risk_id": U("risk/" + k), "assessment_id": ASM, "domain_ids": d, "title": t, "description": t + ".", "severity": sv, "likelihood": lk,
          "finding_ids": [F[f] for f in fl], "mitigation_question": q, "status": st, "owner_user_id": ow, "access": ac}
         for k, d, t, sv, lk, fl, q, st, ow, ac in [
             ("conc", ["traction", "financials"], "Largest customer is 58% of revenue", "high", "likely", ["concentration"], "Is the Nordhafen contract multi-year, and when does it renew?", "open", ANA, "deal_team"),
             ("ip", ["legal"], "No IP assignment for the CTO's pre-incorporation code", "critical", "possible", ["ip"], "Can the company provide a signed assignment covering 2023–2024 work?", "open", MARCO, "deal_team"),
             ("arr", ["financials"], "Deck ARR is 40% higher than the KPI workbook", "high", "likely", ["arr"], "Which ARR definition does the deck use?", "open", PRIYA, "deal_team"),
             ("pentest", ["security"], "No penetration test in the last 12 months", "medium", "possible", ["pentest"], "Is a test planned before the next renewal?", "open", None, "deal_team"),
             ("comp", ["competition"], "Two well-funded incumbents with overlapping products", "medium", "possible", ["market"], "Win rate against incumbents in the last 4 quarters?", "accepted", ANA, "workspace")]]
requests = [{"request_id": U("req/" + k), "assessment_id": ASM, "domain_id": d, "requested_item": it, "reason": r, "blocking": b, "status": st,
             "linked_document_ids": [], "created_by": cb}
            for k, d, it, r, b, st, cb in [
                ("sm", "financials", "Sales and marketing spend by month, last 12 months", "Needed for CAC and payback", False, "sent", "system"),
                ("ip", "legal", "Signed IP assignment from the CTO covering pre-incorporation work", "Legal checklist IP-03", True, "draft", "system"),
                ("arr", "financials", "Which ARR definition the deck uses, with the calculation", "Contradiction: deck vs KPI workbook", True, "sent", "user"),
                ("pt", "security", "Latest penetration test summary", "Security checklist SEC-07", False, "draft", "system")]]

# ---------------- review request ----------------
review = {"target": {"assessment_id": ASM, "assessment_revision": 4, "evidence_snapshot_id": U("ess/104"), "evaluation_id": U("evl/6KQ1"),
                     "memo_version_id": REPORT_ID, "review_policy_version": "single-reviewer@1"},
          "decision": "request_information", "comment": "Need the IP assignment and the ARR definition before IC.",
          "requested_items": ["Signed IP assignment from the CTO covering pre-incorporation work", "Which ARR definition the deck uses, with the calculation"],
          "idempotency_key": "ik_" + U("review/1")[:8]}

# ---------------- domain config ----------------
LV = {"company": [1, 2, 3], "team": [1, 2, 3], "market": [1, 2, 3], "competition": [1, 2, 3], "product": [1, 2, 3], "traction": [1, 2, 3],
      "financials": [2, 3], "capitalization": [1, 2, 3], "legal": [2, 3], "security": [2, 3], "governance": [2, 3], "thesis_fit": [1, 2, 3]}
REQ = {"company", "team", "traction", "financials", "legal", "thesis_fit"}
domain_config = {"config_version": 5, "domains": [
    {"domain_id": k, "enabled": True, "required_for_recommendation": k in REQ, "levels": v, "weight": "0.20" if k in ("team", "market", "product", "traction") else "0.05",
     "min_sources": {str(l): (2 if l == 1 else 4 if l == 2 else 6) for l in v}, "task_budget": {str(l): (3 if l == 1 else 8 if l == 2 else 12) for l in v},
     "overrides": ([{"when": {"industry": ["fintech", "health", "defence"]}, "set": {"required_for_recommendation": True}}] if k == "legal" else
                   [{"when": {"geography": ["EU", "UK"]}, "set": {"min_sources": {"2": 5, "3": 7}}}] if k == "security" else
                   [{"when": {"stage": ["pre-seed", "seed"]}, "set": {"min_sources": {"2": 3, "3": 5}}}] if k == "traction" else [])}
    for k, v in LV.items()]}

# ---------------- events ----------------
CROCK = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
def ulid(ms, n):
    v = (ms << 80) | n; return "".join(CROCK[(v >> (5 * i)) & 31] for i in range(25, -1, -1))
seq, events = {}, []
def ev(dt, typ, kind, sid, aud, data):
    seq[sid] = seq.get(sid, 0) + 1
    events.append({"id": ulid(int(dt.timestamp() * 1000), len(events)), "type": typ, "version": 1, "occurred_at": iso(dt), "sequence": seq[sid],
                   "subject": {"kind": kind, "id": sid}, "audience": aud, "data": data})
t = T0 - timedelta(minutes=30)
ev(t, "assessment.revision_created", "assessment", ASM, "research", {"assessment_id": ASM, "revision": 4, "reason": "upgrade"})
ev(t + timedelta(seconds=1), "run.stage_started", "assessment", ASM, "console", {"assessment_id": ASM, "state": "PLANNING", "stage": "planning", "queue": "q.research", "attempt": 1})
ev(t + timedelta(seconds=14), "document.status_changed", "document", doc_id["signed_contracts.zip"], "research", {"document_id": doc_id["signed_contracts.zip"], "version": 1, "status": "quarantined", "reason": "MALWARE_DETECTED"})
ev(t + timedelta(seconds=40), "assessment.progress", "assessment", ASM, "research", {"assessment_id": ASM, "revision": 4, "stage": "domains_running", "domains_complete": 5, "domains_total": 12, "documents_ready": 7, "documents_total": 9})
ev(t + timedelta(seconds=55), "financials.validation_required", "financial_table", U("ftb/mrr"), "research", {"financial_table_id": U("ftb/mrr"), "version": 1, "issue_count": 3})
ev(t + timedelta(seconds=70), "domain.status_changed", "assessment", ASM, "research", {"assessment_id": ASM, "revision": 4, "domain_id": "security", "status": "failed", "gate_result": "insufficient"})
ev(t + timedelta(seconds=90), "contradiction.detected", "assessment", ASM, "research", {"assessment_id": ASM, "contradiction_id": U("ctr/arr"), "domain_ids": ["financials", "traction"]})
ev(t + timedelta(seconds=95), "risk.updated", "risk", U("risk/arr"), "research", {"risk_id": U("risk/arr"), "severity": "high", "status": "open"})
ev(t + timedelta(seconds=96), "information_request.updated", "information_request", U("req/arr"), "research", {"request_id": U("req/arr"), "status": "draft"})
ev(T0 - timedelta(minutes=12), "report.version_created", "assessment", ASM, "research", {"report_version_id": REPORT_ID, "level": 3, "revision": 4})
ev(T0 - timedelta(minutes=12), "assessment.memo_ready", "assessment", ASM, "research", {"assessment_id": ASM, "memo_version_id": REPORT_ID})
ev(T0 - timedelta(minutes=5), "config.version_created", "config", "cfg", "console", {"version": 5, "changed": ["domains"]})
ev(T0 + timedelta(minutes=9), "financials.validated", "financial_table", U("ftb/mrr"), "research", {"financial_table_id": U("ftb/mrr"), "version": 2, "issue_count": 0})
ev(T0 + timedelta(minutes=9, seconds=2), "assessment.revision_created", "assessment", ASM, "research", {"assessment_id": ASM, "revision": 5, "reason": "new_evidence"})

# ---------------- write + validate ----------------
files = {"assessment_summary.json": (summary, M.AssessmentSummaryView), "assessment_summary_level1.json": (summary_l1, M.AssessmentSummaryView),
         "domains.json": (domains, list[M.DomainStatusSummary]), "findings_sample.json": (findings, list[M.Finding]),
         "report_version.json": (report, M.ReportVersion), "financial_table.json": (table_v1, M.FinancialTable),
         "financial_table_v2_validated.json": (table_v2, M.FinancialTable), "calculations.json": (calcs, list[M.CalculationResult]),
         "risks.json": (risks, list[M.RiskItem]), "information_requests.json": (requests, list[M.InformationRequest]),
         "documents.json": (documents, list[M.DocumentVersion]), "submit_review_request_information.json": (review, M.SubmitReviewRequest),
         "domain_config.json": (domain_config, M.DomainConfigSet)}
from pydantic import TypeAdapter
fails = 0
for name, (obj, model) in files.items():
    dump(name, obj)
    try:
        TypeAdapter(model).validate_json((OUT / name).read_text())
        print(f"PASS {name}")
    except Exception as e:
        fails += 1; print(f"FAIL {name}: {e}")
(OUT / "events.ndjson").write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in events))
for line in (OUT / "events.ndjson").read_text().splitlines():
    e = M.Event.model_validate_json(line)
    need = M.EVENT_DATA_KEYS.get(e.type)
    if need is None or not need <= set(e.data):
        fails += 1; print(f"FAIL event {e.type}: missing {need - set(e.data) if need else 'unknown type'}")
ids = [json.loads(l)["id"] for l in (OUT / "events.ndjson").read_text().splitlines()]
if ids != sorted(ids): fails += 1; print("FAIL events: ids not increasing")
print(f"PASS events.ndjson ({len(events)} events)" if not fails else "")
# negative checks: the validators must reject bad data
neg = [("not_computable with a value", M.CalculationResult, {**calcs[5], "value": "1.1"}),
       ("table v1 claiming it foots", M.FinancialTable, {**table_v1, "checks": [{**c, "passed": True} for c in table_v1["checks"]], "status": "validated", "validated_by": PRIYA}),
       ("request_information without items", M.SubmitReviewRequest, {**review, "requested_items": []}),
       ("thesis_fit disabled", M.DomainConfigSet, {**domain_config, "domains": [{**d, "enabled": d["domain_id"] != "thesis_fit"} for d in domain_config["domains"]]}),
       ("conditions on hold", M.AssessmentSummaryView, {**summary, "recommendation": "hold"}),
       ("private finding with workspace access", M.Finding, {**findings[5], "access": "workspace"}),
       ("report with 20 sections", M.ReportVersion, {**report, "sections": report["sections"][:20]})]
for label, model, bad in neg:
    try:
        model.model_validate(json.loads(json.dumps(bad, default=str))); fails += 1; print(f"FAIL negative: accepted {label}")
    except Exception:
        print(f"PASS negative: rejects {label}")
sys.exit(1 if fails else 0)
