"""SSRF-safe HTTP fetcher (HTTPX) for Temporal Activities.

Blocks private/loopback/link-local/metadata destinations on every DNS resolve
and redirect hop. Does not weaken controls for tests.
"""

from __future__ import annotations

import ipaddress
import socket
import ssl
from collections.abc import Iterable
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

ALLOWED_SCHEMES = frozenset({"http", "https"})
DEFAULT_TIMEOUT = httpx.Timeout(connect=5.0, read=20.0, write=10.0, pool=5.0)
MAX_RESPONSE_BYTES = 5 * 1024 * 1024
MAX_REDIRECTS = 5
ALLOWED_CONTENT_PREFIXES = (
    "text/",
    "application/json",
    "application/xml",
    "application/xhtml",
    "application/pdf",
    "application/atom",
    "application/rss",
)


class SafeFetchError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class SafeFetchResult:
    final_url: str
    status_code: int
    content_type: str
    body: bytes
    redirected: bool
    hops: tuple[str, ...]


class PublicNetworkTransport(httpx.AsyncBaseTransport):
    """Connect to the validated IP, preserving the original HTTP Host and TLS SNI.

    Validation before a normal hostname request is insufficient: the HTTP client
    could resolve the hostname a second time to a private address. No environment
    proxies or hostname connection pools are used here.
    """

    def __init__(self) -> None:
        # IP-keyed pools must never reuse a TLS connection across hostnames that
        # share an address: certificate verification/SNI belongs to each host.
        self._transport = httpx.AsyncHTTPTransport(
            trust_env=False, verify=ssl.create_default_context(), http2=False,
            limits=httpx.Limits(max_keepalive_connections=0)
        )

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        validate_url(str(request.url))
        hostname = request.url.host
        addresses = resolve_and_validate_host(hostname)
        headers = request.headers.copy()
        headers["Host"] = request.url.netloc.decode("ascii")
        pinned = httpx.Request(
            request.method,
            request.url.copy_with(host=addresses[0]),
            headers=headers,
            stream=request.stream,
            extensions={**request.extensions, "sni_hostname": hostname},
        )
        return await self._transport.handle_async_request(pinned)

    async def aclose(self) -> None:
        await self._transport.aclose()


def _is_disallowed_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    ):
        return True
    # Cloud metadata / CGNAT commonly abused ranges
    blocked_nets = [
        ipaddress.ip_network("169.254.0.0/16"),
        ipaddress.ip_network("100.64.0.0/10"),
        ipaddress.ip_network("0.0.0.0/8"),
        ipaddress.ip_network("::1/128"),
        ipaddress.ip_network("fc00::/7"),
        ipaddress.ip_network("fe80::/10"),
    ]
    return any(ip in net for net in blocked_nets)


def resolve_and_validate_host(hostname: str) -> list[str]:
    if not hostname or hostname.lower() in {"localhost", "metadata.google.internal"}:
        raise SafeFetchError("SSRF_BLOCKED", f"disallowed host {hostname!r}")
    try:
        infos = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise SafeFetchError("DNS_FAILED", str(exc)) from exc
    addrs: list[str] = []
    for info in infos:
        ip_str = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError as exc:
            raise SafeFetchError("BAD_IP", ip_str) from exc
        if _is_disallowed_ip(ip):
            raise SafeFetchError("SSRF_BLOCKED", f"resolved to disallowed address {ip}")
        addrs.append(ip_str)
    if not addrs:
        raise SafeFetchError("DNS_EMPTY", hostname)
    return addrs


def validate_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise SafeFetchError("SCHEME_BLOCKED", parsed.scheme)
    if parsed.username or parsed.password:
        raise SafeFetchError("CREDENTIALS_BLOCKED", "userinfo not allowed in URL")
    if not parsed.hostname:
        raise SafeFetchError("HOST_MISSING", url)
    resolve_and_validate_host(parsed.hostname)
    # Strip fragments; never log secrets (no query rewrite of credentials — already blocked)
    return parsed._replace(fragment="").geturl()


def _content_type_allowed(content_type: str | None) -> bool:
    if not content_type:
        return False
    ct = content_type.split(";")[0].strip().lower()
    return any(ct.startswith(p) for p in ALLOWED_CONTENT_PREFIXES)


async def safe_fetch(
    url: str,
    *,
    max_bytes: int = MAX_RESPONSE_BYTES,
    timeout: httpx.Timeout = DEFAULT_TIMEOUT,
    respect_robots: bool = False,
    robots_disallow_paths: Iterable[str] = (),
) -> SafeFetchResult:
    """Fetch with per-hop SSRF validation. Redirects followed manually."""
    current = validate_url(url)
    hops: list[str] = [current]
    redirected = False

    if respect_robots:
        path = urlparse(current).path or "/"
        for blocked in robots_disallow_paths:
            if path.startswith(blocked):
                raise SafeFetchError("ROBOTS_DISALLOW", path)

    async with httpx.AsyncClient(
        transport=PublicNetworkTransport(),
        trust_env=False,
        timeout=timeout,
        follow_redirects=False,
        max_redirects=0,
        headers={
            # Wikimedia and many publishers require a descriptive UA (not a generic bot string).
            "User-Agent": (
                "ThesisDiligenceBot/0.1 (self-hosted VC due-diligence; "
                "+https://github.com/jmpumuro/duligence; research only)"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    ) as client:
        for _ in range(MAX_REDIRECTS + 1):
            # Re-validate every hop (DNS rebinding defense)
            current = validate_url(current)
            try:
                async with client.stream("GET", current) as resp:
                    if resp.status_code in {301, 302, 303, 307, 308}:
                        loc = resp.headers.get("location")
                        if not loc:
                            raise SafeFetchError("REDIRECT_MISSING", current)
                        next_url = str(httpx.URL(current).join(loc))
                        validate_url(next_url)
                        hops.append(next_url)
                        current = next_url
                        redirected = True
                        continue

                    ct = resp.headers.get("content-type", "")
                    if not _content_type_allowed(ct):
                        raise SafeFetchError("CONTENT_TYPE_BLOCKED", ct or "missing")

                    chunks: list[bytes] = []
                    size = 0
                    async for chunk in resp.aiter_bytes():
                        size += len(chunk)
                        if size > max_bytes:
                            raise SafeFetchError("RESPONSE_TOO_LARGE", str(size))
                        chunks.append(chunk)
                    body = b"".join(chunks)
                    return SafeFetchResult(
                        final_url=current,
                        status_code=resp.status_code,
                        content_type=ct.split(";")[0].strip().lower(),
                        body=body,
                        redirected=redirected,
                        hops=tuple(hops),
                    )
            except SafeFetchError:
                raise
            except httpx.TimeoutException as exc:
                raise SafeFetchError("TIMEOUT", str(exc)) from exc
            except httpx.HTTPError as exc:
                raise SafeFetchError("HTTP_ERROR", str(exc)) from exc

    raise SafeFetchError("TOO_MANY_REDIRECTS", str(MAX_REDIRECTS))
