"""Company screening activities — Stage 5 agent pipeline (public Level 1/2)."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from temporalio import activity

from thesis_api.db.models import AssessmentRow
from thesis_api.db.session import SessionLocal
from thesis_api.services.llm_gateway import ExternalAINotAuthorized, public_complete
from thesis_api.services.outbox import enqueue_outbox
from thesis_api.services.progress_store import append_progress_event
from thesis_api.services.review_store import open_review_target
from thesis_api.services.assessment_view import (
    build_measures_from_gates_and_claims,
    requests_from_assessment,
    risks_from_assessment,
)
from thesis_api.services.screening import (
    AGENT_PIPELINE,
    build_screening_memo,
    plan_domains,
    recommend_from_gates,
    run_domain_gate,
)
from thesis_api.services.screening_research import research_domain_claims
from thesis_api.settings import settings
from thesis_api.tenant import TenantContext
from thesis_api.tenant_rls import activate_tenant_rls
from thesis_contracts.lifecycle import transition
from thesis_contracts.review import ReviewTarget

logger = logging.getLogger("thesis_screening")


# Domain-specific angles — prevent cross-domain claim clones.
_DOMAIN_CLAIM_FOCUS: dict[str, str] = {
    "company": (
        "Focus ONLY on legal/operating identity: what the company is, HQ or jurisdiction "
        "if stated, founding narrative, and core offering. Do not discuss competitors, "
        "funding, or market size."
    ),
    "team": (
        "Focus ONLY on named founders, executives, or board members and their stated roles "
        "or prior experience. If no names appear in the passages, say public team identity "
        "is not evidenced on the cited pages — do not invent people."
    ),
    "market": (
        "Focus ONLY on customer segment, industry category, or market positioning stated "
        "on the pages. Do not invent TAM/SAM figures; if size is not cited, say so."
    ),
    "competition": (
        "Focus ONLY on named competitors, alternatives, or differentiation vs peers if "
        "stated. If none are named, say competitive set is not evidenced publicly here."
    ),
    "product": (
        "Focus ONLY on product/platform capabilities, packaging, or pricing signals on "
        "the pages. Avoid fundraising or headcount."
    ),
    "traction": (
        "Focus ONLY on customers, usage, growth, or logos if explicitly stated. "
        "Do not invent ARR, user counts, or growth rates; if absent, say traction "
        "metrics are not evidenced on the cited pages."
    ),
    "financials": (
        "Focus ONLY on revenue, funding rounds, or valuation if explicitly stated with "
        "numbers on the pages. Otherwise say public financial metrics are not evidenced."
    ),
    "capitalization": (
        "Focus ONLY on investors, ownership, or capitalization signals if stated. "
        "Otherwise say cap-table/investor detail is not evidenced on the cited pages."
    ),
    "legal": (
        "Focus ONLY on entity form, litigation, regulation, or compliance statements "
        "on the pages. Otherwise say legal posture is not evidenced publicly here."
    ),
    "security": (
        "Focus ONLY on security, privacy, certifications (e.g. SOC2), or breach notices "
        "if stated. Otherwise say security attestations are not evidenced on the pages."
    ),
    "governance": (
        "Focus ONLY on board, governance, or oversight signals if stated. Otherwise say "
        "governance detail is not evidenced on the cited pages."
    ),
    "thesis_fit": (
        "Focus ONLY on mission, impact, or stated thesis alignment from the pages — "
        "not generic company boilerplate."
    ),
}


async def _public_claim_statement(
    *,
    firm_id: str,
    assessment_id: str,
    revision: int,
    company_name: str,
    domain_id: str,
    passages: list[str] | None = None,
    source_urls: list[str] | None = None,
) -> tuple[str, bool]:
    """Return (statement, used_llm). Prefer evidence-grounded, domain-specific claims."""
    focus = _DOMAIN_CLAIM_FOCUS.get(
        domain_id,
        f"Focus only on diligence signals relevant to the '{domain_id}' domain.",
    )
    evidence_block = ""
    cleaned: list[str] = []
    for p in passages or []:
        t = (p or "").strip()
        if len(t) < 40:
            continue
        if t.startswith("Offline public stub") or t.startswith("Retrieved public page"):
            continue
        cleaned.append(t[:900])
    if cleaned:
        joined = "\n---\n".join(cleaned[:3])
        urls = ", ".join((source_urls or [])[:4]) or "(urls omitted)"
        evidence_block = f"\nCited public passages:\n{joined}\n\nSource URLs: {urls}\n"

    fallback = f"{company_name}: public {domain_id} signal not yet evidenced on cited pages"
    if not settings.openai_api_key.strip():
        if cleaned:
            # Deterministic, domain-tagged stub when LLM unavailable but pages exist.
            return (
                f"{company_name} [{domain_id}]: {cleaned[0][:180].rstrip()}…",
                False,
            )
        return fallback, False

    prompt = (
        f"Company: {company_name}\n"
        f"Diligence domain: {domain_id}\n"
        f"Domain instructions: {focus}\n"
        f"{evidence_block}\n"
        "Write ONE concise factual diligence claim (max 40 words) for THIS domain only. "
        "Ground the claim in the cited passages when provided; do not reuse wording that "
        "would fit every domain. "
        "Do NOT invent funding amounts, valuations, headcount, user counts, or years "
        "unless those exact figures appear in the passages. "
        "If passages are missing or irrelevant to this domain, say what is not evidenced. "
        "Return only the claim sentence."
    )
    try:
        text = await public_complete(
            firm_id=firm_id,
            purpose="extract_claims",
            prompt=prompt,
            assessment_id=UUID(assessment_id),
            revision=revision,
            system=(
                "You extract public-source diligence claims that are domain-specific. "
                "Never use private data. Never invent numeric fundraising, valuation, "
                "user, or headcount figures. Never emit the same claim shape for every domain."
            ),
            max_tokens=120,
        )
        if text:
            return text.splitlines()[0].strip()[:500], True
    except ExternalAINotAuthorized as exc:
        logger.info("llm denied for claim: %s", exc)
    except Exception as exc:  # noqa: BLE001
        logger.warning("llm claim failed: %s", exc)
    if cleaned:
        return f"{company_name} [{domain_id}]: {cleaned[0][:180].rstrip()}…", False
    return fallback, False


async def _public_memo_headline(
    *,
    firm_id: str,
    assessment_id: str,
    revision: int,
    company_name: str,
    level: int,
    recommendation: str,
    domain_gates: dict[str, str],
) -> tuple[str, bool]:
    if not settings.openai_api_key.strip():
        return f"{company_name} — Level {level} screening", False
    gates = ", ".join(f"{k}={v}" for k, v in sorted(domain_gates.items()))
    prompt = (
        f"Company: {company_name}\nLevel: {level}\nRecommendation: {recommendation}\n"
        f"Domain gates: {gates}\n\n"
        "Write a one-sentence diligence headline (max 28 words) for partners. "
        "Public evidence only. No private data."
    )
    try:
        text = await public_complete(
            firm_id=firm_id,
            purpose="summarize_section",
            prompt=prompt,
            assessment_id=UUID(assessment_id),
            revision=revision,
            system="You draft concise VC diligence headlines from public evidence.",
            max_tokens=80,
        )
        if text:
            return text.splitlines()[0].strip()[:280], True
    except ExternalAINotAuthorized as exc:
        logger.info("llm denied for memo: %s", exc)
    except Exception as exc:  # noqa: BLE001
        logger.warning("llm memo failed: %s", exc)
    return f"{company_name} — Level {level} screening", False


@activity.defn(name="screening_set_state")
async def screening_set_state(
    firm_id: str,
    user_id: str,
    assessment_id: str,
    to_state: str,
    expected_revision: int | None = None,
) -> dict[str, Any]:
    from thesis_api.services.workflow_reconcile import spine_rank
    from thesis_contracts.lifecycle import can_transition

    tenant = TenantContext(firm_id=firm_id, user_id=user_id, roles=("operator",))
    async with SessionLocal() as session:
        await activate_tenant_rls(session, firm_id)
        row = (
            await session.execute(select(AssessmentRow).where(AssessmentRow.id == assessment_id))
        ).scalar_one_or_none()
        if row is None:
            return {"ok": False, "error": "NOT_FOUND"}
        tenant.assert_firm(row.firm_id)
        if expected_revision is not None and int(row.revision or 1) != int(expected_revision):
            # Superseded by deepen / request_research — do not fight the new revision.
            return {
                "ok": True,
                "skipped": "STALE_REVISION",
                "state": row.state,
                "revision": row.revision,
            }
        if row.state == to_state:
            return {"ok": True, "state": row.state, "revision": row.revision}
        if can_transition(row.state, to_state):  # type: ignore[arg-type]
            row.state = transition(row.state, to_state)  # type: ignore[arg-type]
        else:
            cur_r = spine_rank(row.state)
            nxt_r = spine_rank(to_state)
            if cur_r is not None and nxt_r is not None and cur_r > nxt_r:
                return {
                    "ok": True,
                    "skipped": "ALREADY_PAST",
                    "state": row.state,
                    "revision": row.revision,
                }
            row.state = transition(row.state, to_state)  # type: ignore[arg-type]
        await append_progress_event(
            session,
            tenant,
            assessment_id=assessment_id,
            revision=row.revision,
            event_type="assessment.status",
            message=to_state,
            data={"status": to_state},
        )
        await enqueue_outbox(
            session,
            firm_id=firm_id,
            subject_type="assessment",
            subject_id=assessment_id,
            event_type="assessment.state_changed",
            idempotency_key=f"state:{assessment_id}:{to_state}:{row.revision}",
            payload={
                "state": to_state,
                "revision": row.revision,
                "company_name": row.company_name,
            },
        )
        await session.commit()
        return {"ok": True, "state": row.state, "revision": row.revision}


@activity.defn(name="screening_plan")
async def screening_plan(level: int) -> dict[str, Any]:
    domains = plan_domains(level)  # type: ignore[arg-type]
    return {
        "agents": list(AGENT_PIPELINE),
        "domains": domains,
        "level": level,
        "llm_enabled": bool(settings.openai_api_key.strip()),
    }


@activity.defn(name="screening_research_domain")
async def screening_research_domain(
    firm_id: str,
    user_id: str,
    assessment_id: str,
    domain_id: str,
    company_name: str,
    level: int,
) -> dict[str, Any]:
    tenant = TenantContext(firm_id=firm_id, user_id=user_id, roles=("operator",))
    async with SessionLocal() as session:
        await activate_tenant_rls(session, firm_id)
        row = (
            await session.execute(select(AssessmentRow).where(AssessmentRow.id == assessment_id))
        ).scalar_one_or_none()
        if row is None:
            return {"ok": False, "error": "NOT_FOUND"}
        tenant.assert_firm(row.firm_id)

        await append_progress_event(
            session,
            tenant,
            assessment_id=assessment_id,
            revision=row.revision,
            event_type="domain.status",
            message=f"{domain_id} researching",
            domain_id=domain_id,
            data={"status": "active"},
        )

        async def _draft_claim(
            passages: list[str], source_urls: list[str]
        ) -> tuple[str, bool]:
            return await _public_claim_statement(
                firm_id=firm_id,
                assessment_id=assessment_id,
                revision=row.revision,
                company_name=company_name,
                domain_id=domain_id,
                passages=passages,
                source_urls=source_urls,
            )

        summary = dict(row.summary_json or {})
        website = (
            str(summary.get("website") or summary.get("primary_domain") or "").strip()
            or None
        )
        research = await research_domain_claims(
            session,
            tenant,
            assessment_id=assessment_id,
            revision=row.revision,
            domain_id=domain_id,
            company_name=company_name,
            draft_statement=_draft_claim,
            website=website,
        )
        used_llm = bool(research.get("used_llm"))
        statement = str(research.get("statement") or "")
        claims = research["claims"]
        contradictions = research["contradictions"]
        stored = research["claim"]
        gate = run_domain_gate(
            assessment_id=UUID(assessment_id),
            revision=row.revision,
            level=level,  # type: ignore[arg-type]
            domain_id=domain_id,  # type: ignore[arg-type]
            claims=claims,
            contradictions=contradictions,
        )

        await append_progress_event(
            session,
            tenant,
            assessment_id=assessment_id,
            revision=row.revision,
            event_type="domain.status",
            message=f"{domain_id} completed",
            domain_id=domain_id,
            data={
                "status": "completed",
                "claims_verified": 1 if gate["gate_result"] != "insufficient" else 0,
                "claims_total": len(claims),
                "contradictions_detected": len(contradictions),
                "evidence_sufficiency": gate["gate_result"],
                "llm_used": used_llm,
                "fetched": research.get("fetched"),
                "independent_count": (research.get("corroboration") or {}).get(
                    "independent_count"
                ),
                "snapshot_id": research.get("snapshot_id"),
                "deep_pass": bool(research.get("deep_pass")),
                "fetched_domain_count": len(
                    (research.get("discovery") or {}).get("fetched_domains") or []
                ),
            },
        )
        await session.commit()
        return {
            "ok": True,
            "domain_id": domain_id,
            "claim_id": str(stored.claim_id),
            "statement": statement,
            "llm_used": used_llm,
            "fetched": research.get("fetched"),
            "deep_pass": bool(research.get("deep_pass")),
            "snapshot_id": research.get("snapshot_id"),
            "span_id": research.get("span_id"),
            "source_url": research.get("source_url"),
            "discovery": research.get("discovery"),
            "contradiction_id": research.get("contradiction_id"),
            "corroboration": research.get("corroboration"),
            "gate": gate,
        }


@activity.defn(name="screening_finalize_memo")
async def screening_finalize_memo(
    firm_id: str,
    user_id: str,
    assessment_id: str,
    domain_gates: dict[str, str],
    company_name: str,
    level: int,
) -> dict[str, Any]:
    tenant = TenantContext(firm_id=firm_id, user_id=user_id, roles=("operator",))
    recommendation = recommend_from_gates(domain_gates, level=level)  # type: ignore[arg-type]
    memo = build_screening_memo(
        company_name=company_name,
        level=level,  # type: ignore[arg-type]
        domain_gates=domain_gates,
        recommendation=recommendation,
    )
    evidence_snapshot_id = uuid4()
    evaluation_id = uuid4()
    memo_version_id = uuid4()

    async with SessionLocal() as session:
        await activate_tenant_rls(session, firm_id)
        row = (
            await session.execute(select(AssessmentRow).where(AssessmentRow.id == assessment_id))
        ).scalar_one_or_none()
        if row is None:
            return {"ok": False, "error": "NOT_FOUND"}
        tenant.assert_firm(row.firm_id)

        headline, llm_used = await _public_memo_headline(
            firm_id=firm_id,
            assessment_id=assessment_id,
            revision=row.revision,
            company_name=company_name,
            level=level,
            recommendation=recommendation,
            domain_gates=domain_gates,
        )
        memo["headline"] = headline
        memo["llm_used"] = llm_used

        summary = dict(row.summary_json or {})
        target = ReviewTarget(
            assessment_id=UUID(assessment_id),
            assessment_revision=row.revision,
            evidence_snapshot_id=evidence_snapshot_id,
            evaluation_id=evaluation_id,
            memo_version_id=memo_version_id,
            review_policy_version="review-policy@1",
        )
        measures = build_measures_from_gates_and_claims(
            domain_gates=domain_gates,
            claim_count=len(domain_gates),
            contested=1 if "company" in domain_gates else 0,
            verified=0,
        )
        risks = risks_from_assessment(
            domain_gates=domain_gates,
            open_contradictions=0,
            company_name=company_name,
        )
        info_reqs = requests_from_assessment(domain_gates=domain_gates, level=level)
        conditions: list[str] = []
        if any(g == "partial" for g in domain_gates.values()):
            conditions.append("Partial domain gates need primary-source confirmation")
        if any(g == "insufficient" for g in domain_gates.values()):
            conditions.append("Open workstream gaps remain — do not treat as diligence-complete")
        summary.update(
            {
                "headline": headline,
                "recommendation": recommendation,
                "memo": memo,
                "domain_gates": domain_gates,
                "measures": measures,
                "risks": risks,
                "requests": info_reqs,
                "conditions": conditions,
                "review_target": target.model_dump(mode="json"),
                "llm_used": llm_used,
            }
        )
        row.summary_json = summary
        if row.state == "CRITIQUING":
            row.state = transition(row.state, "MEMO_READY")  # type: ignore[arg-type]
        elif row.state != "MEMO_READY":
            return {
                "ok": False,
                "error": f"INVALID_STATE:{row.state}",
            }

        await open_review_target(session, tenant, assessment=row, target=target)

        await append_progress_event(
            session,
            tenant,
            assessment_id=assessment_id,
            revision=row.revision,
            event_type="stage",
            message="memo ready",
            data={
                "status": row.state,
                "human_review_status": "pending",
                "partial_results": any(g != "sufficient" for g in domain_gates.values()),
                "llm_used": llm_used,
            },
        )
        await enqueue_outbox(
            session,
            firm_id=firm_id,
            subject_type="assessment",
            subject_id=assessment_id,
            event_type="assessment.memo_ready",
            idempotency_key=f"memo:{assessment_id}:{row.revision}",
            payload={
                "recommendation": recommendation,
                "llm_used": llm_used,
                "company_name": row.company_name,
            },
        )
        await session.commit()
        return {
            "ok": True,
            "state": row.state,
            "recommendation": recommendation,
            "headline": headline,
            "llm_used": llm_used,
            "memo": memo,
            "review_target": target.model_dump(mode="json"),
        }
