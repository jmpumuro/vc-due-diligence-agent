import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

from temporalio.testing import ActivityEnvironment
from thesis_api.services.research_activity import research_heartbeat
from thesis_api.temporal_app.workflows import CompanyScreeningWorkflow


def test_cancel_signal_cancels_inflight_research_handles():
    workflow = CompanyScreeningWorkflow()
    handle = SimpleNamespace(cancel=Mock())
    workflow._research_handles.append(handle)
    workflow.cancel_assessment()
    assert workflow.progress()["cancelled"] is True
    handle.cancel.assert_called_once()


def test_research_heartbeat_runs_in_temporal_activity_context():
    environment = ActivityEnvironment()
    heartbeats = []
    environment.on_heartbeat = lambda *details: heartbeats.append(details)

    async def job():
        async with research_heartbeat():
            await asyncio.sleep(0.01)

    asyncio.run(environment.run(job))
    assert heartbeats
