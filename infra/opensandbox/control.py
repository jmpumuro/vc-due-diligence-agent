"""Pinned control-plane hardening until upstream exposes read-only/tmpfs options.

Run on a dedicated Docker host. Never install this control plane in an agent image.
"""

import os
import secrets
from importlib.metadata import version
from pathlib import Path


def install_hardening() -> None:
    if version("opensandbox-server") != "1.2.0":
        raise RuntimeError("control-plane hardening requires opensandbox-server==1.2.0")
    import asyncio

    from fastapi import HTTPException
    from opensandbox_server.services.docker.container_ops import DockerContainerOpsMixin
    from opensandbox_server.services.docker.docker_service import DockerSandboxService
    from opensandbox_server.services.docker.runtime import DockerRuntimeMixin
    from prepare import verified_profile

    seccomp = verified_profile()

    original = DockerContainerOpsMixin._base_host_config_kwargs

    def bounded_filesystem(self, *args, **kwargs):
        options = original(self, *args, **kwargs)
        options["security_opt"] = [
            opt for opt in options.get("security_opt", []) if not opt.startswith("seccomp=")
        ] + ["seccomp=" + seccomp]
        options["read_only"] = True
        options["tmpfs"] = {
            "/tmp": "rw,nosuid,nodev,size=96m,mode=1777",
            "/run": "rw,nosuid,nodev,size=8m",
            "/home/researcher": "rw,nosuid,nodev,size=16m,uid=10000,gid=10000",
        }
        options["shm_size"] = "64m"
        return options

    DockerContainerOpsMixin._base_host_config_kwargs = bounded_filesystem
    ensure_directory = DockerRuntimeMixin._ensure_directory

    def existing_runtime_volume(self, container, path, *args, **kwargs):
        if path == "/opt/opensandbox":
            # Present in the pinned runtime image and mounted as a managed volume.
            # Docker rejects put_archive('/') against a read-only root filesystem.
            return
        return ensure_directory(self, container, path, *args, **kwargs)

    DockerRuntimeMixin._ensure_directory = existing_runtime_volume
    create = DockerSandboxService.create_sandbox
    admission_lock = asyncio.Lock()

    async def bounded_admission(self, request):
        # One active control-plane process per dedicated Docker host. Admission
        # holds through create so concurrent workers cannot exceed the global cap.
        async with admission_lock:
            live = await asyncio.to_thread(
                self.docker_client.containers.list,
                all=True, filters={"label": "opensandbox.io/id"},
            )
            if len(live) >= 6:
                raise HTTPException(429, "sandbox host capacity exhausted")
            if (
                request.timeout is None or request.timeout > 300
                or request.volumes or request.env or request.extensions
                or request.network_policy is None
                or request.network_policy.default_action != "deny"
            ):
                raise HTTPException(400, "research runtime policy rejected create request")
            response = await create(self, request)
            try:
                sidecars = await asyncio.to_thread(
                    self.docker_client.containers.list,
                    filters={"label": f"opensandbox.io/egress-sidecar-for={response.id}"},
                )
                if len(sidecars) != 1:
                    raise RuntimeError("research egress sidecar missing")
                def limit_sidecar():
                    # docker-py's update wrapper omits PidsLimit, although the
                    # Engine API supports it. Send one bounded host-config update.
                    api = self.docker_client.api
                    update = api._post_json(api._url("/containers/{0}/update", sidecars[0].id), data={
                        "Memory":384 * 1024 * 1024, "MemorySwap":384 * 1024 * 1024,
                        "CpuPeriod":100000, "CpuQuota":50000, "PidsLimit":128,
                    })
                    api._raise_for_status(update)

                await asyncio.to_thread(limit_sidecar)
                # The unprivileged workload must not reach its own execd or vault
                # control ports through the shared loopback namespace.
                for command in [
                    ["nft", "insert", "rule", "inet", "opensandbox", "egress", "tcp", "dport", "18081",
                     "fib", "daddr", "type", "local", "accept"],
                    ["nft", "add", "table", "inet", "thesis_guard"],
                    ["nft", "add", "chain", "inet", "thesis_guard", "output",
                     "{ type filter hook output priority -200; policy accept; }"],
                    ["nft", "add", "rule", "inet", "thesis_guard", "output", "meta", "skuid", "10000",
                     "tcp", "dport", "{ 44772, 18080 }", "reject"],
                ]:
                    status, _ = await asyncio.to_thread(sidecars[0].exec_run, command)
                    if status != 0:
                        raise RuntimeError("research control-port firewall failed")
                return response
            except BaseException:
                await asyncio.to_thread(self.delete_sandbox, response.id)
                raise

    DockerSandboxService.create_sandbox = bounded_admission


if __name__ == "__main__":
    key_file = Path(os.environ.get("THESIS_SANDBOX_KEY_FILE", "var/opensandbox/api-key"))
    if "OPENSANDBOX_SERVER_API_KEY" not in os.environ:
        key_file.parent.mkdir(parents=True, exist_ok=True)
        if not key_file.exists():
            descriptor = os.open(key_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w") as stream:
                stream.write(secrets.token_urlsafe(32))
        os.environ["OPENSANDBOX_SERVER_API_KEY"] = key_file.read_text().strip()
    install_hardening()
    from opensandbox_server.cli import main

    main()
