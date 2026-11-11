"""Live acceptance checks. Requires the dedicated control plane and runtime image."""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "apps/api/src"), str(ROOT / "packages/contracts/src")]

from thesis_api.services.fetch.sandbox_executor import SandboxExecutor
from thesis_api.settings import Settings
from thesis_contracts.public_fetch import PublicFetchRequest


def record(report, args):
    data = json.dumps(report, indent=2) + "\n"
    print(data, end="")
    if args.output:
        destination = Path(args.output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(data)


async def run(args):
    image = (await asyncio.to_thread(
        subprocess.check_output,
        ["docker", "image", "inspect", args.image, "--format", "{{.Id}}"], text=True
    )).strip()
    executor = SandboxExecutor(Settings(
        sandbox_image=image, sandbox_api_key=Path(args.key_file).read_text().strip(),
        sandbox_endpoint=args.endpoint,
    ))
    started = time.monotonic()
    if args.lifecycle:
        from sandbox_probe import lifecycle_probe

        record(await lifecycle_probe(executor), args)
        return
    if args.vault:
        from sandbox_probe import vault_probe

        record(await vault_probe(executor), args)
        return
    if args.diagnose_browser or args.security:
        from sandbox_probe import probe

        record(await probe(executor, browser=args.diagnose_browser), args)
        return
    result = await executor.fetch(PublicFetchRequest(url="https://example.com/"))
    assert result.status_code == 200 and b"Example Domain" in result.body
    report = {"http_fetch": "passed", "duration_seconds": round(time.monotonic() - started, 2),
              "image": image, "sdk": "1.2.0"}
    if args.browser:
        rendered = await executor.fetch(PublicFetchRequest(url="https://example.com/"), render=True)
        assert b"Example Domain" in rendered.body
        report["browser"] = "passed"
    record(report, args)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", default="thesis-research:pilot")
    parser.add_argument("--endpoint", default="http://127.0.0.1:8095")
    parser.add_argument("--key-file", default="var/opensandbox/api-key")
    parser.add_argument("--browser", action="store_true")
    parser.add_argument("--security", action="store_true")
    parser.add_argument("--vault", action="store_true")
    parser.add_argument("--lifecycle", action="store_true")
    parser.add_argument("--output", help="Write a sanitized JSON verification report")
    parser.add_argument("--diagnose-browser", action="store_true")
    asyncio.run(run(parser.parse_args()))
