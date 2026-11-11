# OpenSandbox local acceptance — 2026-11-10

Verified on Docker Desktop Engine 29.9.2 with Python SDK/control plane 1.2.0,
the pinned helper images in `infra/opensandbox/server.toml`, and the research
image digest recorded in the HTTP/browser report. The supplied hardening adapter
and hash-verified Chromium seccomp profile were enabled.

| Check | Evidence |
| --- | --- |
| Public HTTP and Chromium rendering | [http-browser.json](http-browser.json) |
| Network, control ports, filesystem, cross-job files, credential-free environment | [isolation.json](isolation.json) |
| Canary injection, exact-path scoping, redacted metadata, revocation | [vault.json](vault.json) |
| Cancellation and expiry after client loss | [lifecycle.json](lifecycle.json) |

The full regression suite passed **182 tests**, with live PostgreSQL enabled and
migrations through 0010 applied. This included concurrent retry replay, rollback,
cross-tenant reads/writes, cross-tenant assessment references, and deletion cleanup.
The optional sandbox-worker image built successfully with its hashed dependency
export; the Compose override validated. Targeted lint, whitespace, and repository
licence checks passed.

Reproduce the runtime checks using [the setup instructions](../../sandbox-research.md).
The reports contain no application credentials or canary values. These are local
acceptance results, not independent Gate H verification or certification of a
production deployment. No private-document processing or microVM runtime was tested.
