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


async def run_worker() -> None:
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
            activities.playwright_fetch_url,
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
    )
    logger.info("worker polling q.system at %s", settings.temporal_host)
    await worker.run()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
