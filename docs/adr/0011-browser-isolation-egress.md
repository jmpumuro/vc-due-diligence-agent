# ADR-011: Browser isolation and egress proxy

- Status: Accepted
- Date: 2026-11-07

## Decision

All outbound fetch and Playwright render traffic goes through an egress proxy with SSRF controls. The browser worker is isolated (`q.browser`). No CAPTCHA evasion, stealth scraping, or login automation.

## Consequences

SafeFetcher and browser adapters share policy files. Blocked fetches record a reason and never bypass.
