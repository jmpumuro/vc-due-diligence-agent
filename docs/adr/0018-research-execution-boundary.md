# ADR-018: Isolated public-research tools

- Status: Implemented; locally tested on Docker Desktop
- Date: 2026-11-10

## Decision

Offer OpenSandbox as an optional public-tool execution backend. Run public HTTP
fetches and browser renders in disposable jobs. Keep Temporal, model policy,
tenant authorization, corroboration, evidence storage, and frozen report decisions
in the trusted application. Private documents and arbitrary generated code are
outside this backend's scope.

The default Compose installation remains usable without OpenSandbox. An explicitly
selected sandbox backend fails closed on infrastructure errors and never falls
back to local execution or offline evidence stubs.

## Implemented boundaries

| Concern | Implementation |
| --- | --- |
| Inputs and results | Strict public-fetch schemas; bounded URLs, bytes, redirects, content types, hashes, and streamed output. No tenant selectors, model keys, storage destinations, or private text in job inputs. |
| Network | Default-deny `dns+nft`; block private/metadata/host and unapproved public destinations; disable IPv6. HTTP connects to a validated IP with original Host and TLS SNI. Chromium retains its sandbox; unrelated hosts, service workers, and WebSockets are unavailable to the render tool. |
| Credentials | Trusted workers load operator-owned references and provision the vault. HTTPS GET, exact host/path bindings, read-only provider credentials, no authenticated browser or model bindings. Reject common credential reflections before persisting results. |
| Runtime | Fixed commands run as UID/GID 10000. Read-only root; bounded tmpfs, CPU, memory, processes, downloads, outputs, command duration, and mandatory server TTL. No host mounts or Docker socket in jobs. |
| Control plane | Authenticated loopback or HTTPS; job UID cannot reach execd/vault control ports. Single-process admission caps the dedicated host at six live jobs; each worker has a separate concurrency cap. |
| Lifecycle | Heartbeats, cancellation with bounded termination, server-enforced expiry, startup/periodic reconciliation, and explicit cleanup errors. Fresh job/vault state for every call; no reuse or resume API exposed. |
| Retries | PostgreSQL advisory locks and tenant-RLS result records commit with evidence. Concurrent retries reuse committed results; rollback leaves no completion marker. Assessment deletion cascades to retry records. Network caches never retain uncommitted DB identifiers. |
| Packaging | Optional SDK 1.2.0 in the workspace lock, hashed worker/runtime/control-plane requirements, helper image digests, and a hash-verified versioned Playwright seccomp profile. Dedicated optional `q.browser` worker and Compose override. |

The small control-plane adapter is pinned to server 1.2.0 because upstream does
not expose all required read-only/tmpfs, sidecar-limit, and workload-UID firewall
settings. It refuses a different server version. The local proxy-listener
exception permits only the namespace's own data-plane listener; management ports
remain blocked. Upgrades require re-running live acceptance checks.

## Verification

The regression suite covers strict authority boundaries, URL/result integrity,
DNS rebinding, proxy inheritance, browser opt-in, lifecycle cancellation,
credential scoping, and fail-closed errors. Real PostgreSQL tests cover concurrent
retry replay, rollback, tenant isolation, and deletion cleanup. CI runs these
database tests against a migrated service.

Live smoke commands cover HTTP and rendered evidence, private/metadata/host and
unapproved-public blocking, local control-port protection, filesystem and
cross-job isolation, canary credential injection and revocation, cancellation,
and cleanup after a client disappears. Sanitized reports live under
`docs/verification/opensandbox/`.

A body hash detects inconsistent bytes; it does not prove a source is honest.
The vault hides keys from normal job inputs, but allowed requests still exercise
their permissions. Provider-side read-only scopes/quotas and trusted binding
destinations remain necessary. An upstream can reflect credentials in response
bodies; the canary test deliberately checks injection using a disposable value,
while production result validation rejects common reflections.

Local Docker uses a shared kernel. These tests do not establish microVM
containment, production TLS deployment, or a production-ready application.
Independent Gate H, private-data, OCR, and project-wide licence/release gates
remain unchanged.

See [setup, deployment, and acceptance commands](../sandbox-research.md).
