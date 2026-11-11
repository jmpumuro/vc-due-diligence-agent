"""Reconcile expired owned sandboxes after worker or control-plane restarts."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from thesis_api.services.fetch.sandbox_executor import SandboxExecutor
from thesis_api.settings import Settings


async def reap_expired(config: Settings) -> int:
    from opensandbox.exceptions import SandboxApiException
    from opensandbox.manager import SandboxManager
    from opensandbox.models.sandboxes import SandboxFilter

    manager = await SandboxManager.create(connection_config=SandboxExecutor(config).connection())
    try:
        expired = []
        page = 1
        now = datetime.now(UTC)
        async with asyncio.timeout(30):
            while True:
                batch = await manager.list_sandbox_infos(SandboxFilter(
                    metadata={"thesis-owner": config.sandbox_owner}, page=page, page_size=100,
                ))
                for info in batch.sandbox_infos:
                    if (
                        (info.metadata or {}).get("thesis-owner") == config.sandbox_owner
                        and info.expires_at is not None and info.expires_at <= now
                    ):
                        expired.append(info.id)
                if len(batch.sandbox_infos) < 100:
                    break
                page += 1
                if page > 100:
                    raise RuntimeError("sandbox reconciliation page limit exceeded")
            for sandbox_id in expired:
                try:
                    await manager.kill_sandbox(sandbox_id)
                except SandboxApiException as exc:
                    if exc.status_code != 404:
                        raise
        return len(expired)
    finally:
        await manager.close()
