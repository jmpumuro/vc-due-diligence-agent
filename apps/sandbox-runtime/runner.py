"""Fixed public research commands; no shell, models, credentials, or persistence."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import resource
import sys
from pathlib import Path

from safe_fetcher import safe_fetch, validate_url
from thesis_contracts.public_fetch import PublicFetchRequest, PublicFetchResult


async def run(mode: str) -> None:
    if os.getuid() != 10000:
        raise RuntimeError("research commands require the unprivileged uid")
    file_limit = 16 * 1024 * 1024 if mode == "render" else 2_000_000
    descriptor_limit = 1024 if mode == "render" else 128
    resource.setrlimit(resource.RLIMIT_FSIZE, (file_limit, file_limit))
    resource.setrlimit(resource.RLIMIT_NOFILE, (descriptor_limit, descriptor_limit))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    request = PublicFetchRequest.model_validate_json(Path("/tmp/request.json").read_bytes())
    url = validate_url(request.url)
    if mode == "fetch":
        fetched = await safe_fetch(url, max_bytes=request.max_bytes)
        body, final_url, status, content_type, hops = (
            fetched.body, fetched.final_url, fetched.status_code, fetched.content_type, fetched.hops
        )
    elif mode == "render":
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, chromium_sandbox=True)
            try:
                context = await browser.new_context(ignore_https_errors=False, service_workers="block")
                page = await context.new_page()
                chain = [url]

                async def route_request(route):
                    try:
                        validate_url(route.request.url)
                        if route.request.is_navigation_request() and route.request.frame == page.main_frame:
                            target = route.request.url
                            if target != chain[-1]:
                                chain.append(target)
                            if len(chain) > 6:
                                raise ValueError("too many navigation hops")
                        await route.continue_()
                    except Exception as exc:  # noqa: BLE001 -- abort every failed policy check
                        Path("/tmp/render-error.json").write_text(json.dumps({
                            "type":type(exc).__name__, "code":getattr(exc,"code",None)
                        }))
                        await route.abort()

                await context.route("**/*", route_request)
                # No WebSocket capability is needed for public evidence capture.
                await page.route_web_socket("**/*", lambda socket: socket.close())
                response = await page.goto(url, wait_until="domcontentloaded", timeout=20_000)
                body = (await page.content()).encode()
                if len(body) > request.max_bytes:
                    raise ValueError("rendered page exceeds byte budget")
                final_url = validate_url(page.url)
                if chain[-1] != final_url:
                    chain.append(final_url)
                status, content_type, hops = response.status if response else 200, "text/html", tuple(chain)
            finally:
                await browser.close()
    else:
        raise ValueError("unknown fixed command")
    result = PublicFetchResult(
        requested_url=url, final_url=final_url, body=body, status_code=status,
        content_type=content_type, hops=hops, body_sha256=hashlib.sha256(body).hexdigest(),
    )
    Path("/tmp/result.json").write_text(result.model_dump_json())


if __name__ == "__main__":
    try:
        asyncio.run(run(sys.argv[1]))
    except Exception:  # noqa: BLE001 -- suppress untrusted content in command logs
        # No URLs, response content, or SDK tracebacks in sandbox command logs.
        print(json.dumps({"error": "PUBLIC_RESEARCH_FAILED"}))
        sys.exit(1)
