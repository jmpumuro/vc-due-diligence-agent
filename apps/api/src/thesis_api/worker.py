"""Temporal worker entrypoint — Stages 3–8 activities and workflows."""

from __future__ import annotations

import asyncio
import logging

from temporalio.client import Client
from temporalio.worker import Worker

from thesis_api.settings import settings
from thesis_api.temporal_app import activities, outbox_activities, screening_activities
from thesis_api.temporal_app.workflows import (
    CompanyScreeningWorkflow,
    HealthWorkflow,
    OutboxDispatchWorkflow,
    RetentionScanWorkflow,
)

logger = logging.getLogger("thesis_worker")


async def _reconcile_sandboxes() -> None:
    from thesis_api.services.fetch.sandbox_reaper import reap_expired

    while True:
        await asyncio.sleep(30)
        try:
            await reap_expired(settings)
        except Exception:  # noqa: BLE001
            logger.error("sandbox reconciliation failed; server TTL remains active")


async def run_worker() -> None:
    if settings.research_execution_backend == "opensandbox":
        from thesis_api.services.fetch.sandbox_reaper import reap_expired

        await reap_expired(settings)
    client = await Client.connect(settings.temporal_host)
    worker = Worker(
        client,
        task_queue="q.system",
        workflows=[
            HealthWorkflow,
            CompanyScreeningWorkflow,
            OutboxDispatchWorkflow,
            RetentionScanWorkflow,
        ],
        activities=[
            activities.ping,
            activities.safe_fetch_url,
            activities.persist_claim,
            activities.persist_contradiction,
            activities.emit_domain_progress,
            activities.corroborate_sources,
            screening_activities.screening_set_state,
            screening_activities.screening_plan,
            screening_activities.screening_research_domain,
            screening_activities.screening_finalize_memo,
            outbox_activities.outbox_dispatch_pending,
            outbox_activities.retention_scan_due,
        ],
        # Match workflow domain batching (4) with headroom for finalize/outbox.
        max_concurrent_activities=8,
    )
    logger.info("worker polling q.system at %s", settings.temporal_host)
    reconcile = (
        asyncio.create_task(_reconcile_sandboxes())
        if settings.research_execution_backend == "opensandbox" else None
    )
    try:
        await worker.run()
    finally:
        if reconcile is not None:
            reconcile.cancel()
            await asyncio.gather(reconcile, return_exceptions=True)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
