from __future__ import annotations

from typing import Any

from temporalio import activity
from thesis_contracts.public_fetch import PublicFetchRequest
from thesis_contracts.research import Claim, ContradictionRecord

from thesis_api.db.session import SessionLocal
from thesis_api.services.claims_store import insert_claim
from thesis_api.services.contradictions_store import insert_contradiction
from thesis_api.services.corroboration import SourceDocument, rank_and_corroborate
from thesis_api.services.fetch.public_executor import execute_public_fetch
from thesis_api.services.fetch.safe_fetcher import SafeFetchError
from thesis_api.services.fetch.sandbox_executor import SandboxExecutionError
from thesis_api.services.progress_store import append_progress_event
from thesis_api.services.research_activity import research_heartbeat
from thesis_api.tenant import TenantContext


@activity.defn(name="ping")
async def ping() -> str:
    return "pong"


@activity.defn(name="safe_fetch_url")
async def safe_fetch_url(url: str, max_bytes: int = 5_000_000) -> dict[str, Any]:
    """HTTPX SafeFetcher — network only inside activities."""
    try:
        async with research_heartbeat():
            result = await execute_public_fetch(PublicFetchRequest(url=url, max_bytes=min(max_bytes, 900_000)))
        return {
            "ok": True,
            "final_url": result.final_url,
            "status_code": result.status_code,
            "content_type": result.content_type,
            "body_sha256_prefix": __import__("hashlib")
            .sha256(result.body)
            .hexdigest()[:16],
            "byte_length": len(result.body),
            "redirected": len(result.hops) > 1,
            "hops": list(result.hops),
            # Body intentionally omitted from activity result to avoid Temporal payload bloat
            # and accidental secret leakage into workflow history.
        }
    except SandboxExecutionError:
        raise
    except SafeFetchError as exc:
        return {"ok": False, "error_code": exc.code}


@activity.defn(name="playwright_fetch_url")
async def playwright_fetch_url(url: str) -> dict[str, Any]:
    from thesis_api.services.fetch.playwright_fetch import playwright_fetch

    try:
        async with research_heartbeat():
            result = await playwright_fetch(url)
        return {
            "ok": True,
            "final_url": result.final_url,
            "status_code": result.status_code,
            "content_type": result.content_type,
            "title": result.title,
            "html_length": len(result.html),
        }
    except SandboxExecutionError:
        raise
    except SafeFetchError as exc:
        return {"ok": False, "error_code": exc.code}
    except Exception:  # noqa: BLE001
        return {"ok": False, "error_code": "PLAYWRIGHT_ERROR"}


@activity.defn(name="persist_claim")
async def persist_claim(firm_id: str, user_id: str, claim_payload: dict[str, Any]) -> dict[str, Any]:
    claim = Claim.model_validate(claim_payload)
    tenant = TenantContext(firm_id=firm_id, user_id=user_id, roles=("operator",))
    async with SessionLocal() as session:
        stored = await insert_claim(session, tenant, claim)
        await session.commit()
        return stored.model_dump(mode="json")


@activity.defn(name="persist_contradiction")
async def persist_contradiction(
    firm_id: str, user_id: str, contradiction_payload: dict[str, Any]
) -> dict[str, Any]:
    record = ContradictionRecord.model_validate(contradiction_payload)
    tenant = TenantContext(firm_id=firm_id, user_id=user_id, roles=("operator",))
    async with SessionLocal() as session:
        stored = await insert_contradiction(session, tenant, record)
        await session.commit()
        return stored.model_dump(mode="json")


@activity.defn(name="emit_domain_progress")
async def emit_domain_progress(
    firm_id: str,
    user_id: str,
    assessment_id: str,
    revision: int,
    event_type: str,
    message: str,
    domain_id: str | None = None,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tenant = TenantContext(firm_id=firm_id, user_id=user_id, roles=("operator",))
    async with SessionLocal() as session:
        row = await append_progress_event(
            session,
            tenant,
            assessment_id=assessment_id,
            revision=revision,
            event_type=event_type,
            message=message,
            domain_id=domain_id,
            data=data,
        )
        await session.commit()
        return {
            "event_id": row.event_id,
            "assessment_id": assessment_id,
            "event_type": event_type,
        }


@activity.defn(name="corroborate_sources")
async def corroborate_sources(
    claim_key: str,
    documents: list[dict[str, Any]],
    query_terms: list[str],
    contradictory_urls: list[str] | None = None,
) -> dict[str, Any]:
    docs = [
        SourceDocument(
            url=d["url"],
            title=d.get("title") or "",
            snippet=d.get("snippet") or "",
            content_text=d.get("content_text") or "",
            search_rank=d.get("search_rank"),
            is_primary=bool(d.get("is_primary")),
            company_authored=bool(d.get("company_authored")),
        )
        for d in documents
    ]
    result = rank_and_corroborate(
        claim_key=claim_key,
        documents=docs,
        query_terms=query_terms,
        contradictory_urls=contradictory_urls,
    )
    return {
        "claim_key": result.claim_key,
        "independent_count": result.independent_count,
        "independent_domains": result.independent_domains,
        "syndicated_groups": result.syndicated_groups,
        "contradictory_urls": result.contradictory_urls,
        "ranked": [
            {
                "canonical_url": r.canonical_url,
                "domain": r.domain,
                "relevance": str(r.relevance),
                "independence_group": r.independence_group,
                "is_primary": r.is_primary,
                "evidence_quality": r.evidence_quality,
                "company_authored": r.company_authored,
                "search_rank": r.search_rank,
                "near_duplicate_of": r.near_duplicate_of,
                "preserve_despite_low_relevance": r.preserve_despite_low_relevance,
            }
            for r in result.ranked
        ],
    }
