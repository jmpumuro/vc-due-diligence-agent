# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Thesis contributors
"""Investor-safe assessment view enrichment for Level 1–3 tabs."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from thesis_api.db.models import AssessmentRow
from thesis_api.routes.ui_data import synthesize_domains
from thesis_api.services.claims_store import list_claims
from thesis_api.services.contradictions_store import list_contradictions
from thesis_api.services.progress_store import event_to_public_dict, list_progress_events
from thesis_api.tenant import TenantContext


def build_measures_from_gates_and_claims(
    *,
    domain_gates: dict[str, str],
    claim_count: int,
    contested: int,
    verified: int,
    independent_share: str = "mixed",
) -> dict[str, Any]:
    sufficient = sum(1 for g in domain_gates.values() if g == "sufficient")
    partial = sum(1 for g in domain_gates.values() if g == "partial")
    insufficient = sum(1 for g in domain_gates.values() if g == "insufficient")
    scored = sufficient + partial + insufficient
    # Simple L1 attractiveness: 2.5 base + 0.3 per sufficient − 0.4 per insufficient
    score = Decimal("2.5") + Decimal("0.3") * sufficient - Decimal("0.4") * insufficient
    score = max(Decimal("1.0"), min(Decimal("5.0"), score))
    conf_label = "mixed"
    if claim_count and contested == 0 and verified >= max(1, claim_count // 2):
        conf_label = "strong"
    elif contested:
        conf_label = "contested"
    return {
        "source_reliability": {
            "label": independent_share,
            "independent_share": independent_share,
        },
        "claim_confidence": {
            "label": conf_label,
            "verified": verified,
            "source_supported": max(0, claim_count - contested - verified),
            "contested": contested,
            "total": claim_count,
        },
        "evidence_coverage": {
            "domains_sufficient": sufficient,
            "domains_partial": partial,
            "domains_insufficient": insufficient,
            "domains_scored": scored,
        },
        "attractiveness": {
            "score": f"{score:.1f}",
            "range": ["1.0", "5.0"],
            "advance_threshold": "3.5",
        },
    }


def _claims_for_domain(claims: list[Any], domain: str) -> list[Any]:
    return [c for c in claims if str(getattr(c, "domain_id", "") or "") == domain]


def _finding_excerpt(claims: list[Any], *, limit: int = 180) -> str | None:
    for c in claims:
        text = (getattr(c, "statement", None) or "").strip()
        if text:
            return text if len(text) <= limit else f"{text[: limit - 1].rstrip()}…"
    return None


def _source_hosts(claims: list[Any], *, limit: int = 4) -> list[str]:
    hosts: list[str] = []
    seen: set[str] = set()
    for c in claims:
        for u in getattr(c, "source_urls", None) or []:
            if not isinstance(u, str) or not u.startswith("http") or u.endswith("/mirror"):
                continue
            if "example.com" in u:
                continue
            try:
                from urllib.parse import urlparse

                host = (urlparse(u).hostname or "").removeprefix("www.")
            except Exception:  # noqa: BLE001
                continue
            if not host or host in seen:
                continue
            seen.add(host)
            hosts.append(host)
            if len(hosts) >= limit:
                return hosts
    return hosts


def risks_from_assessment(
    *,
    domain_gates: dict[str, str],
    open_contradictions: int,
    company_name: str,
    claims: list[Any] | None = None,
) -> list[dict[str, Any]]:
    """Build the risk register from live gates + agent findings (not static mock copy)."""
    claims = claims or []
    risks: list[dict[str, Any]] = []
    if open_contradictions:
        risks.append(
            {
                "id": "open-contradictions",
                "severity": "medium",
                "likelihood": "high",
                "title": "Open contradictions on public evidence",
                "detail": (
                    f"{open_contradictions} open contradiction(s) remain on {company_name}. "
                    "Partner should resolve or accept risk before advancing."
                ),
                "domain_id": "company",
                "claim_ids": [],
                "source": "agent_contradictions",
            }
        )
    for domain, gate in sorted(domain_gates.items()):
        if gate not in ("partial", "insufficient"):
            continue
        domain_claims = _claims_for_domain(claims, domain)
        excerpt = _finding_excerpt(domain_claims)
        hosts = _source_hosts(domain_claims)
        claim_ids = [str(c.claim_id) for c in domain_claims[:4]]
        label = domain.replace("_", " ")
        if gate == "partial":
            detail = (
                f"Agent finding: “{excerpt}” "
                if excerpt
                else "Public sources only partially corroborate this workstream. "
            )
            if hosts:
                detail += f"Cited: {', '.join(hosts)}. "
            detail += "Treat as directionally useful, not diligence-complete."
            risks.append(
                {
                    "id": f"partial-{domain}",
                    "severity": "medium",
                    "likelihood": "medium",
                    "title": f"{label.title()} needs more diligence",
                    "detail": detail.strip(),
                    "domain_id": domain,
                    "claim_ids": claim_ids,
                    "finding_excerpt": excerpt,
                    "source_hosts": hosts,
                    "gate_result": gate,
                    "source": "agent_gate",
                }
            )
        else:
            detail = (
                f"Agent finding: “{excerpt}” "
                if excerpt
                else f"No partner-grade public evidence cleared {label}. "
            )
            if hosts:
                detail += f"Pages reviewed: {', '.join(hosts)}. "
            detail += "Do not treat this workstream as verified in the memo."
            risks.append(
                {
                    "id": f"insuff-{domain}",
                    "severity": "high",
                    "likelihood": "high",
                    "title": f"{label.title()} evidence gap",
                    "detail": detail.strip(),
                    "domain_id": domain,
                    "claim_ids": claim_ids,
                    "finding_excerpt": excerpt,
                    "source_hosts": hosts,
                    "gate_result": gate,
                    "source": "agent_gate",
                }
            )
    return risks


def requests_from_assessment(
    *,
    domain_gates: dict[str, str],
    level: int,
    claims: list[Any] | None = None,
) -> list[dict[str, Any]]:
    """Draft information asks from thin agent gates — linked to live findings."""
    claims = claims or []
    reqs: list[dict[str, Any]] = []
    for domain, gate in sorted(domain_gates.items()):
        if gate not in ("partial", "insufficient"):
            continue
        domain_claims = _claims_for_domain(claims, domain)
        excerpt = _finding_excerpt(domain_claims)
        label = domain.replace("_", " ")
        detail = (
            "Ask for registry / primary filing confirmation — public identity is still thin."
            if domain == "company"
            else (
                f"Public research left {label} as {gate}. "
                + (f"Latest agent note: “{excerpt}” " if excerpt else "")
                + "Request primary materials (customer proof, deck metrics, or filings) from the company."
            )
        )
        reqs.append(
            {
                "id": f"req-{domain}",
                "domain_id": domain,
                "status": "draft",
                "title": f"Ask company to confirm {label}",
                "detail": detail.strip(),
                "claim_ids": [str(c.claim_id) for c in domain_claims[:3]],
                "gate_result": gate,
                "source": "agent_gate",
            }
        )
    if level < 3:
        reqs.append(
            {
                "id": "req-upgrade-l3",
                "domain_id": "financials",
                "status": "suggested",
                "title": "Open Level 3 for private financials / data room",
                "detail": (
                    "KPI workbook, cap table, and customer contracts are out of Level 1/2 "
                    "public scope — deepen only if partners want private diligence."
                ),
                "claim_ids": [],
                "source": "level_policy",
            }
        )
    return reqs


_FIN_HINTS = (
    "funding",
    "raised",
    "valuation",
    "arr",
    "mrr",
    "revenue",
    "burn",
    "runway",
    "series a",
    "series b",
    "series c",
    "seed round",
    "$",
    "million in",
    "billion in",
    "employees",
)


def public_dataroom_from_claims(claims: list[Any], *, level: int) -> dict[str, Any]:
    """L1/L2: inventory of fetched public evidence (not a private data room)."""
    by_url: dict[str, dict[str, Any]] = {}
    for c in claims:
        urls = list(c.source_urls or [])
        snaps = list(c.snapshot_ids or [])
        for i, url in enumerate(urls):
            if not isinstance(url, str) or not url.startswith("http"):
                continue
            if "example.com" in url or url.endswith("/mirror"):
                continue
            row = by_url.setdefault(
                url,
                {
                    "url": url,
                    "kind": "public_web",
                    "status": "fetched",
                    "domains": set(),
                    "claim_count": 0,
                    "snapshot_ids": set(),
                },
            )
            row["domains"].add(str(c.domain_id))
            row["claim_count"] += 1
            if i < len(snaps):
                row["snapshot_ids"].add(str(snaps[i]))
            for sid in snaps:
                row["snapshot_ids"].add(str(sid))

    documents = [
        {
            "url": v["url"],
            "kind": v["kind"],
            "status": v["status"],
            "domains": sorted(v["domains"]),
            "claim_count": v["claim_count"],
            "snapshot_count": len(v["snapshot_ids"]),
        }
        for v in sorted(by_url.values(), key=lambda x: (-x["claim_count"], x["url"]))
    ]
    return {
        "mode": "public_evidence" if level < 3 else "private_gated",
        "upload_enabled": False,
        "scan_enabled": False,
        "ocr_verified": False,
        "document_count": len(documents),
        "documents": documents,
        "private_documents": [],
        "notice": (
            "Level 1/2 shows public pages SafeFetch already retrieved — not a private data room. "
            "Private uploads unlock at Level 3 when ClamAV is healthy."
            if level < 3
            else "Private data-room uploads are deal-team only; ClamAV-gated when scanner is healthy."
        ),
    }


def public_financials_from_claims(
    claims: list[Any],
    *,
    level: int,
    domain_gates: dict[str, str],
) -> dict[str, Any]:
    """Surface public funding/metric *claims* without inventing ddcalc outputs."""
    signals: list[dict[str, Any]] = []
    for c in claims:
        text = (c.statement or "").strip()
        low = text.lower()
        if not any(h in low for h in _FIN_HINTS):
            continue
        urls = [u for u in (c.source_urls or []) if isinstance(u, str) and u.startswith("http")]
        signals.append(
            {
                "claim_id": str(c.claim_id),
                "domain_id": c.domain_id,
                "statement": text,
                "trust_state": c.trust_state,
                "verification_status": c.verification_status,
                "source_url": urls[0] if urls else None,
                "validated": False,
                "label": "public_claim_unvalidated",
            }
        )

    # L1/L2: never invent blank ARR/burn rows — only surface agent claims that
    # actually mention funding/scale. Calculated metrics appear at Level 3+.
    if level < 3:
        metrics: list[dict[str, Any]] = []
    else:
        metrics = [
            {
                "metric": m,
                "value": None,
                "unit": unit,
                "status": "awaiting_workbook",
                "formula_version": None,
                "note": "Waiting for validated financial table",
            }
            for m, unit in (
                ("ARR", "currency"),
                ("MRR", "currency"),
                ("net_burn", "currency"),
                ("runway_months", "months"),
                ("gross_margin", "ratio"),
            )
        ]
    return {
        "mode": "public_signals" if level < 3 else "private_gated",
        "financials_gate": domain_gates.get("financials", "unavailable_at_level"),
        "validation_queue": [],
        "metrics": metrics,
        "public_signals": signals,
        "signal_count": len(signals),
        "notice": (
            (
                "No ARR/burn calculated from public pages. "
                + (
                    "Rows below are agent claims that mention funding or scale — "
                    "treat as unvalidated until Level 3 tables pass checks."
                    if signals
                    else "No public funding/scale claims extracted yet."
                )
            )
            if level < 3
            else "Deal-team financial validation queue is scaffolded; OCR/ddcalc still gated."
        ),
    }


async def enrich_assessment_payload(
    session: AsyncSession,
    tenant: TenantContext,
    row: AssessmentRow,
) -> dict[str, Any]:
    summary = dict(row.summary_json or {})
    domains = summary.get("domains") or synthesize_domains(row)
    domain_gates = dict(summary.get("domain_gates") or {})
    if not domain_gates:
        domain_gates = {
            d["domain_id"]: d["gate_result"]
            for d in domains
            if d.get("gate_result") not in (None, "unavailable_at_level")
        }

    claims, claim_total = await list_claims(
        session, tenant, assessment_id=row.id, revision=row.revision, limit=200
    )
    contras, contra_total = await list_contradictions(
        session, tenant, assessment_id=row.id, revision=row.revision, limit=100
    )
    open_contras = [c for c in contras if c.resolution == "open"]
    contested = sum(1 for c in claims if c.trust_state == "contested")
    verified = sum(1 for c in claims if c.verification_status == "verified")

    # Stamp contradiction counts onto domain rows (all recorded, not only open)
    contra_by_domain: dict[str, int] = {}
    for c in contras:
        for did in c.domain_ids or []:
            contra_by_domain[str(did)] = contra_by_domain.get(str(did), 0) + 1
    enriched_domains = []
    for d in domains:
        dd = dict(d)
        did = str(dd.get("domain_id") or "")
        if did in contra_by_domain:
            dd["contradictions"] = max(int(dd.get("contradictions") or 0), contra_by_domain[did])
        # findings ≈ claims in domain
        dc = sum(1 for c in claims if c.domain_id == dd.get("domain_id"))
        if dc:
            dd["findings"] = max(int(dd.get("findings") or 0), dc)
        gate = str(dd.get("gate_result") or domain_gates.get(did) or "")
        if gate == "insufficient":
            dd["risks"] = max(int(dd.get("risks") or 0), 1)
            dd["requests"] = max(int(dd.get("requests") or 0), 1)
        elif gate == "partial":
            dd["risks"] = max(int(dd.get("risks") or 0), 1)
            dd["requests"] = max(int(dd.get("requests") or 0), 1)
        # Prefer live sources_found from distinct claim URLs when available.
        host_n = len(
            {
                u
                for c in claims
                if c.domain_id == dd.get("domain_id")
                for u in (c.source_urls or [])
                if isinstance(u, str) and u.startswith("http") and "example.com" not in u
            }
        )
        if host_n:
            dd["sources_found"] = max(int(dd.get("sources_found") or 0), host_n)
        enriched_domains.append(dd)

    # Always rebuild scorecard / risks / asks from live agent claims + gates
    # so tabs never stick to stale scaffold copy after research completes.
    measures = build_measures_from_gates_and_claims(
        domain_gates=domain_gates,
        claim_count=claim_total,
        contested=contested,
        verified=verified,
    )
    risks = risks_from_assessment(
        domain_gates=domain_gates,
        open_contradictions=len(open_contras),
        company_name=row.company_name,
        claims=claims,
    )
    requests = requests_from_assessment(
        domain_gates=domain_gates, level=row.level, claims=claims
    )

    events = await list_progress_events(
        session, tenant, assessment_id=row.id, after_event_id=0, limit=200
    )
    history = [event_to_public_dict(e) for e in events]

    # Always recompute partner conditions from live gates/contradictions —
    # never trust stale summary copy (e.g. false "open contradictions").
    conditions: list[str] = []
    if open_contras:
        conditions.append("Resolve or accept open contradictions before advancing")
    if any(g == "partial" for g in domain_gates.values()):
        conditions.append("Partial domain gates need primary-source confirmation")
    if any(g == "insufficient" for g in domain_gates.values()):
        conditions.append("Open workstream gaps remain — do not treat as diligence-complete")

    memo = dict(summary.get("memo") or {})
    memo["headline"] = summary.get("headline") or memo.get("headline")
    memo["recommendation"] = summary.get("recommendation") or memo.get("recommendation")
    memo["domain_gates"] = domain_gates
    memo["company_name"] = row.company_name
    memo["level"] = row.level

    def _section_body(domain_id: str, gate: str) -> str:
        domain_claims = [c for c in claims if c.domain_id == domain_id]
        supported = [
            c
            for c in domain_claims
            if c.trust_state == "supported" or c.verification_status == "verified"
        ]
        pick = supported or domain_claims
        if pick:
            lead = (pick[0].statement or "").strip()
            hosts = []
            for c in pick[:3]:
                for u in c.source_urls or []:
                    if isinstance(u, str) and u.startswith("http"):
                        try:
                            from urllib.parse import urlparse

                            h = urlparse(u).hostname or ""
                            if h and h not in hosts and "example.com" not in h:
                                hosts.append(h.removeprefix("www."))
                        except Exception:  # noqa: BLE001
                            pass
            host_bit = f" Sources: {', '.join(hosts[:4])}." if hosts else ""
            if gate == "sufficient":
                return f"{lead}{host_bit}"
            if gate == "partial":
                return f"{lead} Gate is partial — treat as directional only.{host_bit}"
            return f"{lead} Workstream remains an open gap until primary evidence clears it.{host_bit}"
        if gate == "insufficient":
            return "No partner-grade public finding cleared this workstream."
        if gate == "partial":
            return "Public sources only partially corroborate this workstream."
        return "No claims recorded for this workstream on the current revision."

    section_ids = [
        ("executive_summary", "Executive summary", None),
        ("company", "Company", "company"),
        ("team", "Team", "team"),
        ("market", "Market", "market"),
        ("product", "Product", "product"),
        ("thesis_fit", "Thesis fit", "thesis_fit"),
    ]
    if row.level >= 2:
        section_ids.extend(
            [
                ("competition", "Competition", "competition"),
                ("traction", "Traction", "traction"),
                ("capitalization", "Capitalization", "capitalization"),
                ("legal", "Legal", "legal"),
                ("security", "Security", "security"),
                ("governance", "Governance", "governance"),
            ]
        )
    if row.level >= 3:
        section_ids.append(("financials", "Financials", "financials"))

    memo["sections"] = []
    for sid, title, domain_id in section_ids:
        if sid == "executive_summary":
            memo["sections"].append(
                {
                    "id": sid,
                    "title": title,
                    "status": "draft",
                    "body": str(summary.get("headline") or memo.get("headline") or "").strip()
                    or "Screening memo draft for partner review.",
                }
            )
            continue
        gate = str(domain_gates.get(domain_id or "", "partial"))
        memo["sections"].append(
            {
                "id": sid,
                "title": title,
                "status": gate,
                "body": _section_body(str(domain_id), gate),
            }
        )

    dataroom = public_dataroom_from_claims(claims, level=row.level)
    if row.level >= 3:
        from sqlalchemy import select

        from thesis_api.db.models_stage6 import DocumentRow
        from thesis_api.services.clamav import ping_clamav

        clam = await ping_clamav()
        upload_ok = bool(clam.get("ok"))
        priv_rows = (
            await session.execute(
                select(DocumentRow)
                .where(
                    DocumentRow.firm_id == tenant.firm_id,
                    DocumentRow.assessment_id == row.id,
                )
                .order_by(DocumentRow.created_at.desc())
                .limit(100)
            )
        ).scalars().all()
        private_docs = [
            {
                "document_id": d.document_id,
                "filename": d.filename,
                "status": d.status,
                "byte_size": d.byte_size,
                "ocr_pages": d.ocr_pages,
                "scan_detail": d.scan_detail,
            }
            for d in priv_rows
        ]
        dataroom.update(
            {
                "upload_enabled": upload_ok,
                "scan_enabled": upload_ok,
                "ocr_verified": False,
                "private_documents": private_docs,
                "private_document_count": len(private_docs),
                "notice": (
                    "ClamAV-gated uploads enabled for the deal team. "
                    "PDF parse via worker-docs; Temporal q.docs Verified still open. Private AI stays off."
                    if upload_ok
                    else "ClamAV unavailable — uploads return SCANNER_UNAVAILABLE until clamd is healthy."
                ),
            }
        )
    financials = public_financials_from_claims(
        claims, level=row.level, domain_gates=domain_gates
    )

    summary.update(
        {
            "domains": enriched_domains,
            "domain_gates": domain_gates,
            "measures": measures,
            "risks": risks,
            "requests": requests,
            "conditions": conditions,
            "memo": memo,
            "claim_total": claim_total,
            "contradiction_total": contra_total,
            "open_contradictions": len(open_contras),
            "history": history,
            "dataroom": dataroom,
            "financials": financials,
            "can_decide": row.state == "AWAITING_REVIEW",
        }
    )
    return {
        "assessment_id": row.id,
        "firm_id": row.firm_id,
        "company_name": row.company_name,
        "level": row.level,
        "state": row.state,
        "revision": row.revision,
        "workflow_id": row.workflow_id,
        "summary": summary,
        "domains": enriched_domains,
        "recommendation": summary.get("recommendation"),
        "headline": summary.get("headline"),
        "measures": measures,
        "conditions": conditions,
        "risks": risks,
        "requests": requests,
        "history": history,
        "dataroom": dataroom,
        "financials": financials,
        "review_target": summary.get("review_target"),
        "can_decide": summary.get("can_decide", False),
        "memo": memo,
        "claim_total": claim_total,
        "contradiction_total": contra_total,
    }
