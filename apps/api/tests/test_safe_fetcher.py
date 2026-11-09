"""SSRF and SafeFetcher security tests — protections must not be weakened."""

from __future__ import annotations

import pytest

from thesis_api.services.fetch.safe_fetcher import SafeFetchError, validate_url


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://localhost/",
        "http://[::1]/",
        "http://169.254.169.254/latest/meta-data/",
        "http://metadata.google.internal/",
        "file:///etc/passwd",
        "ftp://example.com/",
        "http://user:pass@example.com/",
    ],
)
def test_validate_url_blocks_dangerous(url: str) -> None:
    with pytest.raises(SafeFetchError):
        validate_url(url)


def test_validate_url_allows_public_https() -> None:
    # May still fail DNS in offline CI — only assert scheme/host shape when DNS works
    try:
        out = validate_url("https://example.com/path")
        assert out.startswith("https://example.com")
    except SafeFetchError as exc:
        # Offline / DNS failure is acceptable; SSRF codes must not fire for example.com
        assert exc.code in {"DNS_FAILED", "DNS_EMPTY"}


def test_playwright_route_rejects_private() -> None:
    from thesis_api.services.fetch.playwright_fetch import _route_allowed

    assert _route_allowed("http://127.0.0.1/") is False
    assert _route_allowed("file:///tmp/x") is False
