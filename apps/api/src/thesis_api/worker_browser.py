"""Dedicated optional browser queue. Browser execution requires OpenSandbox."""

import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from thesis_api.settings import settings
from thesis_api.temporal_app.activities import playwright_fetch_url


async def main():
    if settings.research_execution_backend != "opensandbox":
        raise RuntimeError("q.browser requires the opensandbox backend")
    client = await Client.connect(settings.temporal_host)
    async with Worker(
        client, task_queue="q.browser", activities=[playwright_fetch_url],
        max_concurrent_activities=settings.sandbox_concurrency,
    ):
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
