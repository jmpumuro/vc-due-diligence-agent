# ADR-011: Browser isolation and egress proxy

- Status: Accepted
- Date: 2026-11-07

## Decision

All outbound fetch and Playwright render traffic goes through an egress proxy with SSRF controls. The browser worker is isolated (`q.browser`). No CAPTCHA evasion, stealth scraping, or login automation.

## Consequences

SafeFetcher and browser adapters share policy files. Blocked fetches record a reason and never bypass.

## Implementation status (2026-11-10)

The optional OpenSandbox backend now implements isolated HTTP/render tools with
default-deny `dns+nft` egress and a separate `q.browser` worker in
`docker-compose.sandbox.yml`. Browser execution requires `BROWSER_ENABLED=true`
and retains Chromium's sandbox. Legacy local rendering still requires an
operator-run SSRF proxy through `BROWSER_EGRESS_PROXY_URL`; local HTTP fetching
pins validated destination IPs. See [ADR-018](0018-research-execution-boundary.md)
and [deployment instructions](../sandbox-research.md).
