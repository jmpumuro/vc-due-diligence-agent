from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from thesis_api.temporal_app import (
        activities,
        docs_activities,
        outbox_activities,
        screening_activities,
    )

# Parallel domain research — preserves evidence quality; caps SearXNG/fetch load.
_DOMAIN_CONCURRENCY = 4


@workflow.defn(name="HealthWorkflow")
class HealthWorkflow:
    @workflow.run
    async def run(self) -> str:
        return await workflow.execute_activity(
            activities.ping,
            start_to_close_timeout=timedelta(seconds=10),
        )


@workflow.defn(name="CompanyScreeningWorkflow")
class CompanyScreeningWorkflow:
    """Level 1/2 public screening spine: plan → research domains → verify → evaluate → critic → memo → review."""

    def __init__(self) -> None:
        self._cancelled = False
        self._research_handles: list[Any] = []

    @workflow.signal
    def cancel_assessment(self) -> None:
        self._cancelled = True
        for handle in self._research_handles:
            handle.cancel()

    @workflow.query
    def progress(self) -> dict[str, Any]:
        return {"cancelled": self._cancelled}

    @workflow.run
    async def run(self, params: dict[str, Any]) -> dict[str, Any]:
        firm_id = params["firm_id"]
        user_id = params["user_id"]
        assessment_id = params["assessment_id"]
        company_name = params["company_name"]
        level = int(params.get("level") or 1)
        expected_revision = int(params["revision"]) if params.get("revision") is not None else None
        timeout = timedelta(seconds=120)
        # Deep pass runs extra SearXNG queries + fetches; allow headroom.
        research_timeout = timedelta(seconds=360)
        retry = RetryPolicy(maximum_attempts=3)

        async def set_state(state: str) -> None:
            await workflow.execute_activity(
                screening_activities.screening_set_state,
                args=[firm_id, user_id, assessment_id, state, expected_revision],
                start_to_close_timeout=timeout,
                retry_policy=retry,
            )

        if self._cancelled:
            return {"ok": False, "cancelled": True}

        await set_state("PLANNING")
        plan = await workflow.execute_activity(
            screening_activities.screening_plan,
            args=[level],
            start_to_close_timeout=timeout,
            retry_policy=retry,
        )
        domains: list[str] = list(plan["domains"])

        await set_state("RESEARCHING")
        domain_gates: dict[str, str] = {}
        for i in range(0, len(domains), _DOMAIN_CONCURRENCY):
            if self._cancelled:
                await set_state("CANCELLED")
                return {"ok": False, "cancelled": True}
            batch = domains[i : i + _DOMAIN_CONCURRENCY]

            async def _research(domain_id: str) -> tuple[str, str]:
                handle = workflow.start_activity(
                    screening_activities.screening_research_domain,
                    args=[firm_id, user_id, assessment_id, domain_id, company_name, level],
                    start_to_close_timeout=research_timeout,
                    retry_policy=retry,
                    heartbeat_timeout=timedelta(seconds=20),
                    cancellation_type=workflow.ActivityCancellationType.WAIT_CANCELLATION_COMPLETED,
                )
                self._research_handles.append(handle)
                try:
                    result = await handle
                finally:
                    self._research_handles.remove(handle)
                gate = (result.get("gate") or {}).get("gate_result") or "insufficient"
                return domain_id, gate

            # Domains are independent claims — run a bounded parallel batch.
            tasks = [asyncio.create_task(_research(d)) for d in batch]
            try:
                outcomes = await asyncio.gather(*tasks)
            except BaseException:
                for handle in self._research_handles:
                    handle.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                if self._cancelled:
                    await set_state("CANCELLED")
                    return {"ok": False, "cancelled": True}
                raise
            for domain_id, gate in outcomes:
                domain_gates[domain_id] = gate

        await set_state("VALIDATING")
        await set_state("EVALUATING")
        # Critic stage: deep follow-up already runs inside research when evidence is thin
        # (bounded second SearXNG+fetch pass). Avoid re-running domains here — that would
        # duplicate claims for the same revision.
        await set_state("CRITIQUING")

        final = await workflow.execute_activity(
            screening_activities.screening_finalize_memo,
            args=[firm_id, user_id, assessment_id, domain_gates, company_name, level],
            start_to_close_timeout=timeout,
            retry_policy=retry,
        )
        return {
            "ok": True,
            "assessment_id": assessment_id,
            "domains": domains,
            "domain_gates": domain_gates,
            "final": final,
            "agents": plan["agents"],
        }


@workflow.defn(name="OutboxDispatchWorkflow")
class OutboxDispatchWorkflow:
    """Drain pending outbox rows into notifications (+ optional webhook)."""

    @workflow.run
    async def run(self, params: dict[str, Any] | None = None) -> dict[str, Any]:
        firm_id = (params or {}).get("firm_id")
        return await workflow.execute_activity(
            outbox_activities.outbox_dispatch_pending,
            args=[firm_id],
            start_to_close_timeout=timedelta(seconds=120),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )


@workflow.defn(name="RetentionScanWorkflow")
class RetentionScanWorkflow:
    """Stage 8: list data rooms past delete_after; destructive delete only with flag."""

    @workflow.run
    async def run(self, params: dict[str, Any] | None = None) -> dict[str, Any]:
        firm_id = (params or {}).get("firm_id")
        return await workflow.execute_activity(
            outbox_activities.retention_scan_due,
            args=[firm_id],
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )


@workflow.defn(name="DocumentIngestionWorkflow")
class DocumentIngestionWorkflow:
    """q.docs: mark parsing → fetch object → worker-docs OCR/parse → persist status."""

    @workflow.run
    async def run(self, params: dict[str, Any]) -> dict[str, Any]:
        firm_id = params["firm_id"]
        document_id = params["document_id"]
        timeout = timedelta(seconds=180)
        retry = RetryPolicy(maximum_attempts=3)

        await workflow.execute_activity(
            docs_activities.docs_mark_status,
            args=[firm_id, document_id, "parsing"],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=retry,
        )
        parsed = await workflow.execute_activity(
            docs_activities.docs_fetch_and_parse,
            args=[firm_id, document_id],
            start_to_close_timeout=timeout,
            retry_policy=retry,
        )
        if not parsed.get("ok"):
            detail = str(parsed.get("error") or "PARSE_FAILED")
            await workflow.execute_activity(
                docs_activities.docs_mark_status,
                args=[firm_id, document_id, "parse_failed", detail, None],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=retry,
            )
            return {"ok": False, "document_id": document_id, "status": "parse_failed", "error": detail}

        status = str(parsed.get("status") or "ready")
        ocr_pages = parsed.get("ocr_pages")
        detail = str(parsed.get("detail") or "q.docs ready")
        await workflow.execute_activity(
            docs_activities.docs_mark_status,
            args=[firm_id, document_id, status, detail, ocr_pages],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=retry,
        )
        return {
            "ok": True,
            "document_id": document_id,
            "status": status,
            "ocr_pages": ocr_pages,
            "methods": parsed.get("methods"),
            "page_count": parsed.get("page_count"),
        }
