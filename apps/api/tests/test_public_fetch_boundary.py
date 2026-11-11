"""Regression coverage for the pre-sandbox trust boundary; no external network."""

import asyncio
import hashlib
import socket

import httpx
import pytest
from pydantic import ValidationError
from thesis_api.services.fetch import safe_fetcher
from thesis_api.services.fetch.public_executor import validate_public_result
from thesis_contracts.public_fetch import PublicFetchRequest, PublicFetchResult


@pytest.fixture
def public_dns(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))],
    )


def result(**changes):
    values = {
        "requested_url": "https://example.com/",
        "final_url": "https://example.com/",
        "status_code": 200,
        "content_type": "text/html",
        "body": b"public evidence",
        "body_sha256": hashlib.sha256(b"public evidence").hexdigest(),
        "hops": ("https://example.com/",),
    }
    return PublicFetchResult(**(values | changes))


@pytest.mark.parametrize("field", ["firm_id", "credentials", "model_api_key", "database_url"])
def test_request_cannot_carry_authority(field):
    with pytest.raises(ValidationError):
        PublicFetchRequest(url="https://example.com/", **{field: "secret"})


def test_private_scope_rejected():
    with pytest.raises(ValidationError):
        PublicFetchRequest(url="https://example.com/", scope="private")


def test_result_integrity_and_json_roundtrip():
    original = result(body=b"\xff\x00", body_sha256=hashlib.sha256(b"\xff\x00").hexdigest())
    assert PublicFetchResult.model_validate_json(original.model_dump_json()) == original
    with pytest.raises(ValidationError, match="hash mismatch"):
        result(body=b"tampered")
    with pytest.raises(ValidationError, match="redirect chain"):
        result(final_url="https://other.example/")
    with pytest.raises(ValidationError):
        result(firm_id="another-tenant")


def test_result_bound_to_request_and_size(public_dns):
    with pytest.raises(safe_fetcher.SafeFetchError, match="RESULT_REQUEST_MISMATCH"):
        validate_public_result(PublicFetchRequest(url="https://other.example/"), result())
    with pytest.raises(safe_fetcher.SafeFetchError, match="RESPONSE_TOO_LARGE"):
        validate_public_result(PublicFetchRequest(url="https://example.com/", max_bytes=1), result())


def test_private_redirect_rejected_on_trusted_side(public_dns, monkeypatch):
    def resolve(host):
        if host == "internal.example":
            raise safe_fetcher.SafeFetchError("SSRF_BLOCKED", "private")
        return ["93.184.216.34"]

    monkeypatch.setattr(safe_fetcher, "resolve_and_validate_host", resolve)
    malicious = result(
        final_url="http://internal.example/",
        hops=("https://example.com/", "http://internal.example/"),
    )
    with pytest.raises(safe_fetcher.SafeFetchError, match="SSRF_BLOCKED"):
        validate_public_result(PublicFetchRequest(url="https://example.com/"), malicious)


def test_transport_pins_ip_preserving_host_sni(public_dns, monkeypatch):
    observed = []

    async def upstream(request):
        observed.append(request)
        return httpx.Response(200, headers={"content-type": "text/html"}, content=b"evidence")

    monkeypatch.setattr(httpx, "AsyncHTTPTransport", lambda **kw: httpx.MockTransport(upstream))

    async def run():
        fetched = await safe_fetcher.safe_fetch("https://example.com:8443/path")
        assert fetched.final_url == "https://example.com:8443/path"

    asyncio.run(run())
    assert observed[0].url.host == "93.184.216.34"
    assert observed[0].url.port == 8443
    assert observed[0].headers["host"] == "example.com:8443"
    assert observed[0].extensions["sni_hostname"] == "example.com"


def test_rebinding_before_connect_fails_closed(monkeypatch):
    answers = iter(["93.184.216.34", "93.184.216.34", "93.184.216.34", "127.0.0.1"])

    def dns(*args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (next(answers), 0))]

    async def must_not_connect(request):
        pytest.fail("connection attempted after private DNS answer")

    monkeypatch.setattr(socket, "getaddrinfo", dns)
    monkeypatch.setattr(
        httpx, "AsyncHTTPTransport", lambda **kw: httpx.MockTransport(must_not_connect)
    )
    with pytest.raises(safe_fetcher.SafeFetchError, match="SSRF_BLOCKED"):
        asyncio.run(safe_fetcher.safe_fetch("https://example.com/"))


def test_redirect_to_metadata_never_connects(public_dns, monkeypatch):
    seen = []
    original = safe_fetcher.resolve_and_validate_host

    def resolve(host):
        if host == "169.254.169.254":
            raise safe_fetcher.SafeFetchError("SSRF_BLOCKED", "metadata")
        return original(host)

    async def upstream(request):
        seen.append(request)
        return httpx.Response(302, headers={"location": "http://169.254.169.254/latest/"})

    monkeypatch.setattr(safe_fetcher, "resolve_and_validate_host", resolve)
    monkeypatch.setattr(httpx, "AsyncHTTPTransport", lambda **kw: httpx.MockTransport(upstream))
    with pytest.raises(safe_fetcher.SafeFetchError, match="SSRF_BLOCKED"):
        asyncio.run(safe_fetcher.safe_fetch("https://example.com/"))
    assert len(seen) == 1


def test_transport_disables_environment_proxy_and_connection_reuse(monkeypatch):
    options = []

    def transport(**kwargs):
        options.append(kwargs)
        return httpx.MockTransport(lambda request: httpx.Response(200))

    monkeypatch.setattr(httpx, "AsyncHTTPTransport", transport)
    asyncio.run(safe_fetcher.PublicNetworkTransport().aclose())
    assert options[0]["trust_env"] is False
    assert options[0]["http2"] is False
    assert options[0]["limits"].max_keepalive_connections == 0


def test_executor_keeps_original_urls_through_relative_redirect(public_dns, monkeypatch):
    from thesis_api.services.fetch.public_executor import execute_public_fetch

    async def upstream(request):
        if request.url.path == "/":
            return httpx.Response(302, headers={"location": "/evidence"})
        return httpx.Response(200, headers={"content-type": "text/plain"}, content=b"facts")

    monkeypatch.setattr(httpx, "AsyncHTTPTransport", lambda **kw: httpx.MockTransport(upstream))
    fetched = asyncio.run(execute_public_fetch(PublicFetchRequest(url="https://example.com/")))
    assert fetched.final_url == "https://example.com/evidence"
    assert fetched.hops == ("https://example.com/", "https://example.com/evidence")
    assert fetched.body == b"facts"


def test_browser_disabled_or_missing_proxy_fails_closed(monkeypatch):
    from thesis_api.services.fetch.playwright_fetch import playwright_fetch
    from thesis_api.settings import settings

    monkeypatch.setattr(settings, "browser_enabled", False)
    with pytest.raises(safe_fetcher.SafeFetchError, match="BROWSER_DISABLED"):
        asyncio.run(playwright_fetch("https://example.com/"))
    monkeypatch.setattr(settings, "browser_enabled", True)
    monkeypatch.setattr(settings, "browser_egress_proxy_url", "")
    with pytest.raises(safe_fetcher.SafeFetchError, match="BROWSER_PROXY_REQUIRED"):
        asyncio.run(playwright_fetch("https://example.com/"))


def test_browser_keeps_chromium_sandbox_and_uses_proxy(public_dns, monkeypatch):
    import sys
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from thesis_api.services.fetch.playwright_fetch import playwright_fetch
    from thesis_api.settings import settings

    monkeypatch.setattr(settings, "browser_enabled", True)
    monkeypatch.setattr(settings, "browser_egress_proxy_url", "http://egress:8080")
    page = SimpleNamespace(
        route=AsyncMock(), goto=AsyncMock(return_value=None),
        url="https://example.com/", content=AsyncMock(return_value="<p>evidence</p>"),
        title=AsyncMock(return_value="Example"),
    )
    browser = SimpleNamespace(
        new_context=AsyncMock(return_value=SimpleNamespace(new_page=AsyncMock(return_value=page))),
        close=AsyncMock(),
    )
    chromium = SimpleNamespace(launch=AsyncMock(return_value=browser))
    context = SimpleNamespace(chromium=chromium)
    # Special methods must live on the class for async-with lookup.
    class Manager:
        async def __aenter__(self):
            return context

        async def __aexit__(self, *args):
            return False

    monkeypatch.setitem(sys.modules, "playwright", SimpleNamespace())
    monkeypatch.setitem(
        sys.modules, "playwright.async_api", SimpleNamespace(async_playwright=Manager)
    )
    asyncio.run(playwright_fetch("https://example.com/"))
    options = chromium.launch.call_args.kwargs
    assert options["chromium_sandbox"] is True
    assert "--no-sandbox" not in options["args"]
    assert options["proxy"] == {"server": "http://egress:8080"}
    browser.close.assert_awaited_once()
