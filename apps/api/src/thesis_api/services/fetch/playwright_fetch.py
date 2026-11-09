"""Isolated Playwright fetch with SafeFetcher-equivalent network policy.

Browser subresources and redirects are gated by the same SSRF rules.
Requires playwright only when invoked (optional dependency for CI without browsers).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from thesis_api.services.fetch.safe_fetcher import (
    SafeFetchError,
    validate_url,
)


@dataclass(frozen=True)
class PlaywrightFetchResult:
    final_url: str
    status_code: int | None
    content_type: str
    html: str
    title: str | None


def _route_allowed(url: str) -> bool:
    try:
        parsed = urlparse(url)
        if parsed.scheme in {"data", "blob", "about"}:
            return False
        if parsed.scheme not in {"http", "https"}:
            return False
        validate_url(url)
        return True
    except SafeFetchError:
        return False


async def playwright_fetch(
    url: str,
    *,
    timeout_ms: int = 20_000,
    max_html_chars: int = 1_500_000,
) -> PlaywrightFetchResult:
    """Render a JS-heavy page under SSRF-equivalent egress controls."""
    validate_url(url)
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise SafeFetchError(
            "PLAYWRIGHT_UNAVAILABLE",
            "playwright not installed; use HTTP SafeFetcher or install browsers",
        ) from exc

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--no-sandbox"],
        )
        try:
            context = await browser.new_context(
                java_script_enabled=True,
                ignore_https_errors=False,
                user_agent="ThesisPlaywrightFetcher/0.1",
            )
            page = await context.new_page()

            async def on_route(route: Any) -> None:
                req_url = route.request.url
                if not _route_allowed(req_url):
                    await route.abort()
                    return
                await route.continue_()

            await page.route("**/*", on_route)
            response = await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            # Re-validate final location (JS redirects)
            final = page.url
            validate_url(final)
            html = await page.content()
            if len(html) > max_html_chars:
                raise SafeFetchError("RESPONSE_TOO_LARGE", str(len(html)))
            title = await page.title()
            status = response.status if response else None
            return PlaywrightFetchResult(
                final_url=final,
                status_code=status,
                content_type="text/html",
                html=html,
                title=title or None,
            )
        finally:
            await browser.close()
