"""Trusted live diagnostics; these commands are never exposed to research agents."""

import asyncio
import hashlib
import json
import secrets
import subprocess
from datetime import timedelta
from pathlib import Path

from opensandbox.models.execd import RunCommandOpts
from opensandbox.models.filesystem import WriteEntry
from opensandbox.models.sandboxes import CredentialProxyConfig
from opensandbox.sandbox import Sandbox
from thesis_api.services.fetch.sandbox_executor import network_policy_for


async def create_test_sandbox(executor, *, ttl=120):
    return await Sandbox.create(
        executor.config.sandbox_image, connection_config=executor.connection(),
        timeout=timedelta(seconds=ttl), ready_timeout=timedelta(seconds=40),
        resource={"cpu":"1", "memory":"768Mi"},
        metadata={"thesis-owner":executor.config.sandbox_owner},
        network_policy=network_policy_for("https://example.com/"),
    )

NETWORK_PROBE = '''
import json, os, socket
from pathlib import Path
out = {"uid": os.getuid(), "blocked": {}}
targets = [("metadata", "169.254.169.254",80), ("private", "10.0.0.1",80),
           ("host", "172.17.0.1",8095), ("other-public", "1.1.1.1",443),
           ("vault", "127.0.0.1",18080), ("execd", "127.0.0.1",44772),
           ("ipv6-loopback", "::1",44772), ("ipv6-private", "fd00::1",80)]
for name, host, port in targets:
    try:
        with socket.create_connection((host,port), timeout=0.5):
            out["blocked"][name] = False
    except OSError:
        out["blocked"][name] = True
out["no_docker_socket"] = not Path("/var/run/docker.sock").exists()
out["no_cross_job_file"] = not Path("/tmp/other-job-marker").exists()
out["no_application_secrets"] = not any(k in os.environ for k in
    ["OPENAI_API_KEY","DATABASE_URL","S3_SECRET_KEY","SANDBOX_API_KEY","OPENSANDBOX_EGRESS_TOKEN"])
out["tmp_limit_bytes"] = os.statvfs("/tmp").f_blocks * os.statvfs("/tmp").f_frsize
try:
    Path("/opt/research/forbidden").write_text("no")
    out["root_readonly"] = False
except OSError:
    out["root_readonly"] = True
print(json.dumps(out))
'''

BROWSER_PROBE = '''
import asyncio, json, os, sys
sys.path.insert(0,"/opt/research")
async def main():
    from runner import run
    try:
        await run("render")
        print(json.dumps({"browser_launch":"passed", "uid":os.getuid()}))
    except Exception as exc:
        from pathlib import Path
        detail = Path("/tmp/render-error.json")
        print(json.dumps({"browser_launch":str(exc)[:6000], "uid":os.getuid(),
                          "route_error": detail.read_text() if detail.exists() else None}))
asyncio.run(main())
'''


async def probe(executor, *, browser=False):
    first = await create_test_sandbox(executor)
    sandbox = None
    try:
        await first.files.write_files([WriteEntry(path="/tmp/other-job-marker", data="isolated", mode=644)])
        sandbox = await create_test_sandbox(executor)
        assert sandbox.id != first.id
        await sandbox.files.write_files([WriteEntry(
            path="/tmp/probe.py", data=BROWSER_PROBE if browser else NETWORK_PROBE, mode=644,
        ), WriteEntry(path="/tmp/request.json", data='{"url":"https://example.com/"}', mode=644)])
        result = await sandbox.commands.run(
            "/usr/local/bin/python /tmp/probe.py",
            opts=RunCommandOpts(timeout=timedelta(seconds=20), uid=10000, gid=10000),
        )
        assert result.exit_code in {0,None} and result.error is None
        payload = json.loads("".join(line.text for line in result.logs.stdout))
        if not browser:
            assert payload["uid"] == 10000
            assert all(payload["blocked"].values()), payload
            assert all(payload[k] for k in ["no_docker_socket", "no_application_secrets", "root_readonly", "no_cross_job_file"])
            assert payload["tmp_limit_bytes"] <= 96 * 1024 * 1024
        return payload
    finally:
        if sandbox is not None:
            await sandbox.destroy()
        await first.destroy()


async def lifecycle_probe(executor):
    from unittest.mock import patch

    from thesis_contracts.public_fetch import PublicFetchRequest

    original_create = Sandbox.create
    started = asyncio.Event()
    observed = []

    async def create_slow_job(*args, **kwargs):
        sandbox = await original_create(*args, **kwargs)
        observed.append(sandbox.id)
        original_run = sandbox.commands.run

        async def slow_command(*args, **kwargs):
            started.set()
            return await original_run("sleep 30", **kwargs)

        sandbox.commands.run = slow_command
        return sandbox

    async def containers(sandbox_id):
        return (await asyncio.to_thread(subprocess.check_output,
            ["docker", "ps", "-a", "--filter", f"label=opensandbox.io/id={sandbox_id}",
             "--format", "{{.ID}}"], text=True)).strip()

    with patch.object(Sandbox, "create", create_slow_job):
        task = asyncio.create_task(executor.fetch(PublicFetchRequest(url="https://example.com/")))
        try:
            await asyncio.wait_for(started.wait(), timeout=50)
        except BaseException:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            raise
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        else:
            raise AssertionError("research cancellation was not propagated")
    assert observed and not await containers(observed[0])
    # Drop the client handle without destroying the sandbox, as a crashed worker
    # would. The independently running control plane must expire it by its TTL.
    orphan = await create_test_sandbox(executor, ttl=60)
    orphan_id = orphan.id
    await orphan.close()
    try:
        async with asyncio.timeout(80):
            while await containers(orphan_id):
                await asyncio.sleep(2)
    finally:
        if await containers(orphan_id):
            await orphan.destroy()
    return {"cancellation_cleanup":"passed", "worker_loss_ttl_cleanup":"passed"}


async def vault_probe(executor):
    canary = secrets.token_urlsafe(32)
    digest = hashlib.sha256(canary.encode()).hexdigest()
    sandbox = await Sandbox.create(
        executor.config.sandbox_image, connection_config=executor.connection(),
        timeout=timedelta(seconds=120), ready_timeout=timedelta(seconds=40),
        resource={"cpu":"1", "memory":"768Mi"},
        metadata={"thesis-owner":executor.config.sandbox_owner},
        network_policy=network_policy_for("https://httpbin.org/bearer"),
        credential_proxy=CredentialProxyConfig(enabled=True),
    )
    try:
        await sandbox.credential_vault.create(
            credentials=[{"name":"canary", "source":{"value":canary}}],
            bindings=[{"name":"canary", "match":{"schemes":["https"], "hosts":["httpbin.org"],
                        "methods":["GET"], "paths":["/bearer"]},
                       "auth":{"type":"bearer", "credential":"canary"}}],
        )
        metadata = await sandbox.credential_vault.get()
        assert canary not in str(metadata)
        source = '''
import asyncio, hashlib, json, os, sys
sys.path.insert(0,"/opt/research")
from safe_fetcher import safe_fetch
async def main():
    result = await safe_fetch("https://httpbin.org/bearer", max_bytes=10000)
    token = json.loads(result.body).get("token", "")
    expected = EXPECTED_HASH
    assert hashlib.sha256(token.encode()).hexdigest() == expected
    assert all(hashlib.sha256(v.encode()).hexdigest() != expected for v in os.environ.values())
    other = await safe_fetch("https://httpbin.org/headers", max_bytes=10000)
    assert "Authorization" not in json.loads(other.body)["headers"]
    print(json.dumps({"credential_injected":True,"env_secret_absent":True,"other_path_uncredentialed":True}))
asyncio.run(main())
'''.replace("EXPECTED_HASH", repr(digest))
        await sandbox.files.write_files([WriteEntry(path="/tmp/vault-probe.py", data=source, mode=644)])
        execution = await sandbox.commands.run(
            "/usr/local/bin/python /tmp/vault-probe.py",
            opts=RunCommandOpts(timeout=timedelta(seconds=25), uid=10000, gid=10000),
        )
        assert canary not in str(execution)
        assert execution.error is None and execution.exit_code in {0,None}, (
            "vault request probe failed: " + str(execution)[:6000]
        )
        output = json.loads("".join(line.text for line in execution.logs.stdout))
        await sandbox.credential_vault.delete()
        # Re-run after revocation: the same command cannot authenticate anymore.
        revoked = await sandbox.commands.run(
            "/usr/local/bin/python /tmp/vault-probe.py",
            opts=RunCommandOpts(timeout=timedelta(seconds=25), uid=10000, gid=10000),
        )
        assert revoked.error is not None or revoked.exit_code not in {0,None}
        output["revocation"] = "passed"
        output["metadata_redacted"] = True
        return output
    except BaseException:
        sidecar = (await asyncio.to_thread(subprocess.check_output, [
            "docker", "ps", "--filter", f"label=opensandbox.io/egress-sidecar-for={sandbox.id}",
            "--format", "{{.ID}}",
        ], text=True)).strip()
        if sidecar:
            rules = await asyncio.to_thread(subprocess.check_output,
                ["docker", "exec", sidecar, "nft", "list", "ruleset"], text=True)
            Path("var/opensandbox/last-vault-rules.txt").write_text(rules)
        raise
    finally:
        await sandbox.destroy()
