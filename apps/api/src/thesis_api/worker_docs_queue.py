# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Thesis contributors
"""Temporal worker for q.docs (DocumentIngestionWorkflow)."""

from __future__ import annotations

import asyncio
import logging

from temporalio.client import Client
from temporalio.worker import Worker

from thesis_api.settings import settings
from thesis_api.temporal_app import docs_activities
from thesis_api.temporal_app.workflows import DocumentIngestionWorkflow

logger = logging.getLogger("thesis_worker_docs")


async def run_worker() -> None:
    client = await Client.connect(settings.temporal_host)
    worker = Worker(
        client,
        task_queue="q.docs",
        workflows=[DocumentIngestionWorkflow],
        activities=[
            docs_activities.docs_mark_status,
            docs_activities.docs_fetch_and_parse,
        ],
    )
    logger.info("worker polling q.docs at %s", settings.temporal_host)
    await worker.run()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
