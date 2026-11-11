"""Heartbeat long research and coordinate cancellation with sandbox cleanup."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from temporalio import activity


@asynccontextmanager
async def research_heartbeat():
    async def heartbeat():
        while True:
            activity.heartbeat("research-running")
            await asyncio.sleep(5)

    task = asyncio.create_task(heartbeat())
    try:
        yield
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
