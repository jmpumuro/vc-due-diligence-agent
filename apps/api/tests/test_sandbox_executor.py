"""Security/lifecycle tests against the pinned SDK interfaces; no live network."""

import asyncio
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import SecretStr, ValidationError

pytest.importorskip("opensandbox")

from datetime import UTC

from opensandbox.sandbox import Sandbox
from thesis_api.services.fetch import public_executor, safe_fetcher, sandbox_executor
from thesis_api.services.fetch.sandbox_credentials import ResearchCredential, load_credentials
from thesis_api.services.fetch.sandbox_executor import SandboxExecutionError, SandboxExecutor
from thesis_api.settings import Settings
from thesis_contracts.public_fetch import PublicFetchRequest, PublicFetchResult


@pytest.fixture
def rig(monkeypatch):
    monkeypatch.setattr(safe_fetcher, "resolve_and_validate_host", lambda host: ["93.184.216.34"])
    monkeypatch.setattr(sandbox_executor, "resolve_and_validate_host", lambda host: ["93.184.216.34"])
    body = b"public facts"
    output = PublicFetchResult(
        requested_url="https://example.com/evidence", final_url="https://example.com/evidence",
        status_code=200, content_type="text/plain", body=body,
        body_sha256=hashlib.sha256(body).hexdigest(), hops=("https://example.com/evidence",),
    )
    sandbox = SimpleNamespace(
        id="job-1", destroy=AsyncMock(),
        files=SimpleNamespace(write_files=AsyncMock(), read_bytes=AsyncMock(return_value=output.model_dump_json().encode())),
        commands=SimpleNamespace(run=AsyncMock(return_value=SimpleNamespace(error=None, exit_code=0))),
        credential_vault=SimpleNamespace(create=AsyncMock()),
    )
    async def stream_result(*args, **kwargs):
        data = sandbox.files.read_bytes.return_value
        for offset in range(0, len(data), 65536):
            yield data[offset:offset+65536]

    sandbox.files.read_bytes_stream = AsyncMock(side_effect=stream_result)
    create = AsyncMock(return_value=sandbox)
    monkeypatch.setattr(Sandbox, "create", create)
    config = Settings(_env_file=None, sandbox_api_key="control-secret", sandbox_image="sha256:" + "a" * 64)
    executor = SandboxExecutor(config)
    return executor, sandbox, create


def request():
    return PublicFetchRequest(url="https://example.com/evidence")


def test_disposable_job_has_no_application_authority(rig):
    executor, sandbox, create = rig
    assert asyncio.run(executor.fetch(request())).body == b"public facts"
    kwargs = create.call_args.kwargs
    assert kwargs["env"] == {} and kwargs["volumes"] == []
    assert kwargs["network_policy"].default_action == "deny"
    assert kwargs["timeout"].total_seconds() == 120
    assert kwargs["resource"] == {"cpu": "1", "memory": "768Mi"}
    assert kwargs["credential_proxy"].enabled is False
    assert any(rule.action == "deny" and rule.target == "169.254.0.0/16" for rule in kwargs["network_policy"].egress)
    command = sandbox.commands.run.call_args
    assert command.args[0] == "/usr/local/bin/python /opt/research/runner.py fetch"
    assert command.kwargs["opts"].uid == 10000
    assert "control-secret" not in str(sandbox.files.write_files.call_args)
    sandbox.destroy.assert_awaited_once()


def test_invalid_output_is_rejected_and_cleaned_up(rig):
    executor, sandbox, _ = rig
    sandbox.files.read_bytes.return_value = b'{"firm_id":"another-firm"}'
    with pytest.raises(SandboxExecutionError):
        asyncio.run(executor.fetch(request()))
    sandbox.destroy.assert_awaited_once()


def test_oversized_stream_is_closed_before_parsing(rig):
    executor, sandbox, _ = rig
    closed = []

    async def oversized(*args, **kwargs):
        try:
            for _ in range(30):
                yield b"x" * 65536
        finally:
            closed.append(True)

    sandbox.files.read_bytes_stream = AsyncMock(side_effect=oversized)
    with pytest.raises(SandboxExecutionError):
        asyncio.run(executor.fetch(request()))
    assert closed == [True]
    sandbox.destroy.assert_awaited_once()


@pytest.mark.parametrize("surface", ["encoded_body", "redirect_url"])
def test_reflected_credentials_never_leave_trusted_boundary(rig, tmp_path, monkeypatch, surface):
    import base64

    executor, sandbox, _ = rig
    secret = "disposable-test-credential"
    path = tmp_path / "credentials.json"
    path.write_text(json.dumps([credential_policy()]))
    executor.config.sandbox_credentials_file = str(path)
    monkeypatch.setenv("THESIS_RESEARCH_SECRET_SOURCE", secret)
    previous = PublicFetchResult.model_validate_json(sandbox.files.read_bytes.return_value)
    if surface == "encoded_body":
        body = base64.b64encode(secret.encode())
        changed = previous.model_copy(update={"body":body, "body_sha256":hashlib.sha256(body).hexdigest()})
    else:
        final = previous.final_url + "?token=" + secret
        changed = previous.model_copy(update={"final_url":final, "hops":(previous.requested_url, final)})
    sandbox.files.read_bytes.return_value = changed.model_dump_json().encode()
    with pytest.raises(SandboxExecutionError):
        asyncio.run(executor.fetch(request()))
    sandbox.destroy.assert_awaited_once()


def test_cancellation_waits_for_remote_cleanup(rig):
    executor, sandbox, _ = rig

    async def scenario():
        entered = asyncio.Event()

        async def block(*args, **kwargs):
            entered.set()
            await asyncio.Event().wait()

        sandbox.commands.run.side_effect = block
        task = asyncio.create_task(executor.fetch(request()))
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        sandbox.destroy.assert_awaited_once()
        assert executor.slots._value == executor.config.sandbox_concurrency

    asyncio.run(scenario())


def test_cleanup_failure_prevents_success(rig):
    executor, sandbox, _ = rig
    sandbox.destroy.side_effect = RuntimeError("untrusted SDK detail")
    with pytest.raises(SandboxExecutionError, match="SANDBOX_CLEANUP_FAILED") as failure:
        asyncio.run(executor.fetch(request()))
    assert "untrusted SDK detail" not in str(failure.value)


def test_missing_sdk_or_create_failure_never_falls_back(rig, monkeypatch):
    executor, _, create = rig
    create.side_effect = RuntimeError("secret in upstream error")
    local = AsyncMock()
    monkeypatch.setattr(public_executor, "safe_fetch", local)
    from thesis_api.settings import settings
    monkeypatch.setattr(settings, "research_execution_backend", "opensandbox")
    monkeypatch.setattr(sandbox_executor, "get_executor", lambda: executor)
    with pytest.raises(SandboxExecutionError) as failure:
        asyncio.run(public_executor.execute_public_fetch(request()))
    assert "secret in upstream error" not in str(failure.value)
    local.assert_not_awaited()


def test_control_plane_requires_tls_or_loopback_and_digest(rig):
    executor, _, _ = rig
    executor.config.sandbox_endpoint = "http://control.example.com:8095"
    with pytest.raises(ValueError):
        executor.connection()
    executor.config.sandbox_endpoint = "http://127.0.0.1:8095"
    executor.config.sandbox_image = "thesis-research:latest"
    with pytest.raises(ValueError):
        executor.connection()


def credential_policy(**changes):
    return {
        "name": "research-source", "host": "example.com", "paths": ["/evidence"],
        "secret_env": "THESIS_RESEARCH_SECRET_SOURCE",
    } | changes


@pytest.mark.parametrize("changes", [
    {"host": "*.example.com"}, {"host": "127.0.0.1"}, {"paths": ["/*"]},
    {"paths": ["/../secrets"]}, {"paths": ["/%2fprivate"]}, {"methods": ["POST"]},
    {"secret_env": "OPENAI_API_KEY"},
])
def test_credential_policy_rejects_broad_or_model_authority(changes):
    with pytest.raises(ValidationError):
        ResearchCredential.model_validate(credential_policy(**changes))


def test_vault_provisioned_host_side_for_exact_get_only(rig, tmp_path, monkeypatch):
    executor, sandbox, create = rig
    path = tmp_path / "credentials.json"
    path.write_text(json.dumps([credential_policy()]))
    executor.config.sandbox_credentials_file = str(path)
    monkeypatch.setenv("THESIS_RESEARCH_SECRET_SOURCE", "research-canary")
    asyncio.run(executor.fetch(request()))
    assert create.call_args.kwargs["credential_proxy"].enabled is True
    binding = sandbox.credential_vault.create.call_args.kwargs["bindings"][0]
    assert binding["match"] == {
        "schemes": ["https"], "hosts": ["example.com"], "methods": ["GET"], "paths": ["/evidence"]
    }
    assert "research-canary" not in str(sandbox.files.write_files.call_args)
    assert "research-canary" not in str(sandbox.commands.run.call_args)
    assert isinstance(load_credentials(str(path), request().url)[0][1], SecretStr)
    assert load_credentials(str(path), "https://other.example/evidence") == []
    assert load_credentials(str(path), "https://example.com/other") == []


def test_authenticated_browser_rejected_before_creation(rig, tmp_path, monkeypatch):
    executor, _, create = rig
    path = tmp_path / "credentials.json"
    path.write_text(json.dumps([credential_policy()]))
    executor.config.sandbox_credentials_file = str(path)
    monkeypatch.setenv("THESIS_RESEARCH_SECRET_SOURCE", "research-canary")
    with pytest.raises(SandboxExecutionError):
        asyncio.run(executor.fetch(request(), render=True))
    create.assert_not_awaited()


def test_network_cache_does_not_reuse_uncommitted_database_ids(monkeypatch):
    from thesis_api.services import screening_research as research
    from thesis_api.tenant import TenantContext

    raw = {"fetched":True, "url":"https://example.com/", "passage":"facts", "text":"facts",
           "body":b"facts", "content_type":"text/plain", "status_code":200, "text_len":5}
    monkeypatch.setattr(research, "_FETCH_CACHE", {})
    monkeypatch.setattr(research, "_FETCH_CACHE_LOCK", asyncio.Lock())
    monkeypatch.setattr(research, "_http_fetch_raw", AsyncMock(return_value=raw))
    persistence = AsyncMock(side_effect=[
        (SimpleNamespace(snapshot_id="first"), SimpleNamespace(span_id="first-span")),
        (SimpleNamespace(snapshot_id="second"), SimpleNamespace(span_id="second-span")),
    ])
    monkeypatch.setattr(research, "persist_fetch_evidence", persistence)
    tenant = TenantContext(firm_id="firm", user_id="user", roles=("operator",))

    async def scenario():
        first = await research.fetch_public_evidence(None, tenant, url=raw["url"])
        retry = await research.fetch_public_evidence(None, tenant, url=raw["url"])
        assert first["snapshot_id"] != retry["snapshot_id"]
        assert all("snapshot_id" not in value for value in research._FETCH_CACHE.values())

    asyncio.run(scenario())


@pytest.mark.parametrize("status", [404, 500])
def test_reaper_handles_ttl_race_without_deleting_other_jobs(rig, monkeypatch, status):
    from datetime import datetime, timedelta

    from opensandbox.exceptions import SandboxApiException
    from opensandbox.manager import SandboxManager
    from thesis_api.services.fetch.sandbox_reaper import reap_expired

    executor, _, _ = rig
    now = datetime.now(UTC)
    records = [
        SimpleNamespace(id="expired", metadata={"thesis-owner":executor.config.sandbox_owner}, expires_at=now-timedelta(seconds=1)),
        SimpleNamespace(id="active", metadata={"thesis-owner":executor.config.sandbox_owner}, expires_at=now+timedelta(minutes=1)),
        SimpleNamespace(id="another-owner", metadata={"thesis-owner":"another"}, expires_at=now-timedelta(seconds=1)),
    ]
    manager = SimpleNamespace(
        list_sandbox_infos=AsyncMock(return_value=SimpleNamespace(sandbox_infos=records)),
        kill_sandbox=AsyncMock(side_effect=SandboxApiException(status_code=status)), close=AsyncMock(),
    )
    monkeypatch.setattr(SandboxManager, "create", AsyncMock(return_value=manager))
    if status == 404:
        assert asyncio.run(reap_expired(executor.config)) == 1
    else:
        with pytest.raises(SandboxApiException):
            asyncio.run(reap_expired(executor.config))
    manager.kill_sandbox.assert_awaited_once_with("expired")
    manager.close.assert_awaited_once()
