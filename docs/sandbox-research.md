# Isolated public research

Thesis supports `RESEARCH_EXECUTION_BACKEND=opensandbox` for public HTTP fetching
and browser rendering. Temporal, model-policy decisions, tenant authorization,
evidence validation, and database writes stay in trusted workers. The default
Compose installation continues to use local HTTP fetching; selecting OpenSandbox
fails closed on infrastructure errors, without local execution or offline-stub
fallback. This is a public-tool backend, not a private-document or arbitrary-code
agent environment.

## Local setup

Use a dedicated Docker host for shared installations. Local evaluation can use
Docker Desktop. The control plane needs Docker access and must never run inside
an agent sandbox or share its API key with a job.

From the repository root:

```bash
uv sync --all-packages --extra sandbox
uv venv var/opensandbox/control
uv pip install --python var/opensandbox/control/bin/python \
  --require-hashes -r infra/opensandbox/requirements.txt
var/opensandbox/control/bin/python infra/opensandbox/prepare.py
docker pull opensandbox/execd@sha256:6cf7dba2f21f0b536e100563d841ac58a9f31c2b0a081b7ac76796a24d6f47e2
docker pull opensandbox/egress@sha256:db7345d567b0970f384b8e3fa7a93a71b7f43d4b16bb2009de34096e9a87b3b5
docker build -f apps/sandbox-runtime/Dockerfile -t thesis-research:pilot .
var/opensandbox/control/bin/python infra/opensandbox/control.py \
  --config infra/opensandbox/server.toml
```

The control plane creates `var/opensandbox/api-key` with mode 0600 and listens on
127.0.0.1:8095. Its state and keys are ignored by Git. Do not rebuild/retag the
runtime image during an acceptance run. Use a registry digest for deployment;
the local smoke script resolves the image's immutable local digest itself.

In another terminal:

```bash
uv run --extra sandbox python scripts/smoke_sandbox.py
uv run --extra sandbox python scripts/smoke_sandbox.py --browser
uv run --extra sandbox python scripts/smoke_sandbox.py --security
uv run --extra sandbox python scripts/smoke_sandbox.py --vault
uv run --extra sandbox python scripts/smoke_sandbox.py --lifecycle
```

The vault check sends a disposable random canary to httpbin.org. Its test-only
command compares hashes and emits booleans; it does not use application keys.
The endpoint deliberately reflects a token to verify injection. Never configure
such an endpoint as a production credential binding. Credential secrecy cannot
prevent a trusted upstream from reflecting or otherwise disclosing its inputs.

## Enable workers

For a worker running on the same host, set `SANDBOX_API_KEY` from the local key
file, `SANDBOX_IMAGE` to the immutable image digest, and
`RESEARCH_EXECUTION_BACKEND=opensandbox`. Apply database migrations through 0010
before starting the worker. Set `BROWSER_ENABLED=true` for browser calls.

Containerized workers need an authenticated HTTPS control-plane endpoint with
normal certificate verification. Put a trusted TLS reverse proxy in front of
the loopback control plane on its dedicated host. Configure its certificate
trust for the worker; do not disable TLS verification or expose Docker's socket.
Then use the optional override:

```bash
docker compose -f docker-compose.yml -f docker-compose.sandbox.yml \
  --profile sandbox up --build -d
```

`worker-browser` polls `q.browser`. Browser activities should use that task queue,
a heartbeat timeout of at least 20 seconds, and
`WAIT_CANCELLATION_COMPLETED`. The regular screening worker polls `q.system`.
The browser has no research credentials. Its initial host is allowed; unrelated
CDN hosts, WebSockets, service workers, and external redirect hosts are denied.
Pages that require those resources may be incomplete; fetch those sources as
separate public jobs rather than widening a job's egress policy automatically.

## Credentials

Keep `SANDBOX_CREDENTIALS_FILE` empty for anonymous public research. For an
authenticated source, create an operator-owned JSON file using
`infra/opensandbox/credentials.example.json` and provision its named
`THESIS_RESEARCH_SECRET_*` environment variable only in the trusted worker.
The file holds references, not values. For Compose, mount the policy read-only
in the trusted worker and explicitly add only the required secret environment
variables. Neither belongs in the runtime image or job request.

Bindings allow HTTPS GET to exact hosts and exact non-root paths. Wildcards,
write methods, arbitrary secret-variable names, overlapping bindings, and
routing/framing headers are rejected. Missing credentials fail closed. Use
provider-issued read-only scopes and provider quotas as well: GET and a hidden
key alone cannot constrain every provider's permissions or billing.

Vault configuration is written through the host-side SDK after sandbox creation.
The workload receives no real credential values in its environment, command, or
input file. The egress proxy inserts authentication. Revoke provider credentials
when access is withdrawn; each job is destroyed after use. Pause, resume, reuse,
authenticated browser research, and model credentials are not exposed by this
backend. Jobs always receive a fresh environment and fresh vault state.

## Limits and recovery

Each job has one CPU, 768 MiB RAM, at most 256 processes, a read-only root
filesystem, bounded writable tmpfs mounts, bounded downloads and outputs, and a
mandatory 120-second lifetime (configurable from 60 to 300). Each worker process
admits two jobs by default; the dedicated single-process control plane caps all
live sandboxes at six. Each egress sidecar is capped at 384 MiB RAM, half a CPU,
and 128 processes. Network policy is default deny with `dns+nft`; IPv6 is
disabled. Workloads cannot access their own execd/vault control ports.

The small control-plane adapter is intentionally pinned to server 1.2.0 because
it adds read-only/tmpfs admission settings and a workload-UID firewall that the
upstream configuration does not expose. It refuses an unsupported version.
The seccomp policy preserves Chromium's sandbox and is verified against a pinned
upstream hash. Run live acceptance tests before upgrading any component.

Temporal research activities heartbeat, cancel active jobs, and wait for bounded
cleanup. A mandatory server TTL covers process death or a lost create response.
The worker reconciles expired owned sandboxes at startup and every 30 seconds;
`python -m thesis_api.cli reap-sandboxes` also runs this reconciliation. An orphan
with an unexpired TTL may remain until expiration. Cleanup failure is an error,
not a successful research result.

Committed activity results are stored transactionally with evidence under tenant
RLS. Concurrent retries serialize on a PostgreSQL advisory lock and reuse the
committed result. Assessment deletion cascades to these retry records. Network
caches contain raw responses rather than uncommitted database identifiers.

This local Docker profile uses a shared kernel. Stronger host containment requires
a separately verified gVisor/Kata deployment or dedicated hosts; these tests do
not establish a microVM security boundary. Existing Gate H, private-data, OCR,
and project-wide release gates remain independent.

Sanitized local acceptance reports are under `docs/verification/opensandbox/`.
Pass `--output PATH` to a smoke command to regenerate one. The lifecycle check
takes about a minute because it waits for a real abandoned sandbox to expire.
