"""Disposable public research tools. Secrets and durable state stay host-side."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
from contextlib import aclosing
from datetime import timedelta
from urllib.parse import quote, urlsplit

from thesis_contracts.public_fetch import PublicFetchRequest, PublicFetchResult

from thesis_api.services.fetch.safe_fetcher import (
    SafeFetchError,
    resolve_and_validate_host,
    validate_url,
)
from thesis_api.services.fetch.sandbox_credentials import load_credentials
from thesis_api.settings import Settings

logger = logging.getLogger("thesis_sandbox")
MAX_WIRE_BYTES = 1_250_000
DENIED_NETWORKS = (
    "0.0.0.0/8", "10.0.0.0/8", "100.64.0.0/10", "127.0.0.0/8",
    "169.254.0.0/16", "172.16.0.0/12", "192.168.0.0/16", "198.18.0.0/15",
    "224.0.0.0/4", "240.0.0.0/4", "::/0",
)


class SandboxExecutionError(SafeFetchError):
    """Infrastructure failures must not become offline evidence or local fallback."""


def network_policy_for(url: str):
    from opensandbox.models.sandboxes import NetworkPolicy, NetworkRule

    host = urlsplit(validate_url(url)).hostname
    addresses = resolve_and_validate_host(host)
    rules = [NetworkRule(action="deny", target=network) for network in DENIED_NETWORKS]
    rules.append(NetworkRule(action="allow", target=host))
    rules.extend(NetworkRule(action="allow", target=ip) for ip in addresses)
    return NetworkPolicy(default_action="deny", egress=rules)


class SandboxExecutor:
    def __init__(self, config: Settings):
        self.config = config
        self.slots = asyncio.Semaphore(config.sandbox_concurrency)

    def connection(self):
        from opensandbox.config import ConnectionConfig

        endpoint = urlsplit(self.config.sandbox_endpoint)
        if (
            endpoint.scheme not in {"http", "https"} or not endpoint.hostname
            or endpoint.username or endpoint.password or endpoint.query or endpoint.fragment
            or endpoint.path not in {"", "/"}
            or (endpoint.scheme == "http" and endpoint.hostname not in {"localhost", "127.0.0.1", "::1"})
            or not self.config.sandbox_api_key.get_secret_value()
        ):
            raise ValueError("sandbox requires an authenticated HTTPS or loopback endpoint")
        if not re.fullmatch(r"(?:[^\s]+@)?sha256:[0-9a-f]{64}", self.config.sandbox_image):
            raise ValueError("sandbox image must be pinned by digest")
        return ConnectionConfig(
            domain=endpoint.netloc, protocol=endpoint.scheme,
            api_key=self.config.sandbox_api_key.get_secret_value(),
            request_timeout=timedelta(seconds=40), disable_metrics=True,
        )

    async def fetch(self, request: PublicFetchRequest, *, render: bool = False) -> PublicFetchResult:
        try:
            async with asyncio.timeout(15):
                await self.slots.acquire()
        except TimeoutError:
            raise SandboxExecutionError("SANDBOX_CAPACITY", "research capacity exhausted") from None
        try:
            return await self._fetch(request, render=render)
        except asyncio.CancelledError:
            raise
        except SandboxExecutionError:
            raise
        except Exception:  # noqa: BLE001 -- never expose upstream credential payloads
            # SDK errors/validation errors can contain request URLs and secret payloads.
            raise SandboxExecutionError("SANDBOX_FAILED", "isolated research failed") from None
        finally:
            self.slots.release()

    async def _fetch(self, request: PublicFetchRequest, *, render: bool) -> PublicFetchResult:
        from opensandbox.models.execd import ExecutionHandlers, RunCommandOpts
        from opensandbox.models.filesystem import WriteEntry
        from opensandbox.models.sandboxes import CredentialProxyConfig
        from opensandbox.sandbox import Sandbox

        config = self.connection()
        url = validate_url(request.url)
        credentials = load_credentials(self.config.sandbox_credentials_file, url)
        # A browser receives no credential capability: only the fixed GET tool does.
        if render and credentials:
            raise ValueError("authenticated browser research is not supported")
        sandbox = None
        try:
            async with asyncio.timeout(45):
                sandbox = await Sandbox.create(
                    self.config.sandbox_image, connection_config=config,
                    timeout=timedelta(seconds=self.config.sandbox_timeout_seconds),
                    ready_timeout=timedelta(seconds=40),
                    resource={"cpu": "1", "memory": "768Mi"},
                    metadata={"thesis-owner": self.config.sandbox_owner},
                    env={}, volumes=[],
                    network_policy=network_policy_for(url),
                    credential_proxy=CredentialProxyConfig(enabled=bool(credentials)),
                )
            logger.info("sandbox created id=%s", sandbox.id)
            async with asyncio.timeout(50):
                if credentials:
                    policy, secret = credentials[0]
                    await sandbox.credential_vault.create(
                        credentials=[{"name": policy.name, "source": {"value": secret.get_secret_value()}}],
                        bindings=[{
                            "name": policy.name,
                            "match": {"schemes": ["https"], "hosts": [policy.host],
                                      "methods": ["GET"], "paths": list(policy.paths)},
                            "auth": {"type": policy.auth_type, "credential": policy.name,
                                     **({"name": policy.header_name} if policy.auth_type == "apiKey" else {})},
                        }],
                    )
                    logger.info("sandbox credential provisioned binding=%s id=%s", policy.name, sandbox.id)
                await sandbox.files.write_files([WriteEntry(
                    path="/tmp/request.json", data=request.model_dump_json(), mode=644,
                )])
                logged_bytes = 0

                async def bounded_log(message):
                    nonlocal logged_bytes
                    logged_bytes += len(message.text.encode())
                    if logged_bytes > 4096:
                        raise ValueError("sandbox command output exceeded limit")

                # Fixed literals support the pinned execd's shell API. No URL,
                # credential, agent text, or other variable enters shell syntax.
                command = (
                    "/usr/local/bin/python /opt/research/runner.py render"
                    if render else "/usr/local/bin/python /opt/research/runner.py fetch"
                )
                execution = await sandbox.commands.run(
                    command,
                    opts=RunCommandOpts(timeout=timedelta(seconds=35), uid=10000, gid=10000),
                    handlers=ExecutionHandlers(on_stdout=bounded_log, on_stderr=bounded_log),
                )
                if execution.error or execution.exit_code not in {0, None}:
                    raise ValueError("sandbox command failed")
                payload = bytearray()
                stream = await sandbox.files.read_bytes_stream(
                    "/tmp/result.json", range_header=f"bytes=0-{MAX_WIRE_BYTES}"
                )
                async with aclosing(stream) as chunks:
                    async for chunk in chunks:
                        if len(payload) + len(chunk) > MAX_WIRE_BYTES:
                            raise ValueError("sandbox output exceeded limit")
                        payload.extend(chunk)
                result = PublicFetchResult.model_validate_json(payload)
                # Never trust the sandbox's own hash to establish request authority.
                from thesis_api.services.fetch.public_executor import validate_public_result

                result = validate_public_result(request, result)
                for _, secret in credentials:
                    value = secret.get_secret_value()
                    variants = (
                        value.encode(), quote(value, safe="").encode(),
                        json.dumps(value)[1:-1].encode(), base64.b64encode(value.encode()),
                        base64.urlsafe_b64encode(value.encode()),
                    )
                    if any(variant in result.body or variant in payload for variant in variants):
                        raise ValueError("credential reflected in response")
                return result
        finally:
            if sandbox is not None:
                # Cancellation must wait for bounded remote termination. Server TTL
                # and the reaper cover process death or a lost create response.
                cleanup = asyncio.create_task(self._destroy(sandbox))
                try:
                    await asyncio.shield(cleanup)
                except asyncio.CancelledError:
                    await cleanup
                    raise

    async def _destroy(self, sandbox) -> None:
        from opensandbox.exceptions import SandboxApiException

        try:
            async with asyncio.timeout(15):
                await sandbox.destroy()
        except SandboxApiException as exc:
            if exc.status_code != 404:
                logger.error("sandbox cleanup failed id=%s; server TTL remains active", sandbox.id)
                raise SandboxExecutionError("SANDBOX_CLEANUP_FAILED", "termination requires reconciliation") from None
        except Exception:  # noqa: BLE001 -- sanitize upstream errors, which may contain secrets
            logger.error("sandbox cleanup failed id=%s; server TTL remains active", sandbox.id)
            raise SandboxExecutionError("SANDBOX_CLEANUP_FAILED", "termination requires reconciliation") from None


_executor: SandboxExecutor | None = None


def get_executor() -> SandboxExecutor:
    global _executor
    if _executor is None:
        from thesis_api.settings import settings

        _executor = SandboxExecutor(settings)
    return _executor
