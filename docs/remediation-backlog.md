# Remediation backlog (integrated with ongoing implementation)

**Rule.** Do not restart the project. Preserve working code and tests. Track unresolved pre-implementation items as technical debt with explicit dependencies and release gates. Address security-critical issues **before** implementing dependent features. Do **not** mark the application production-ready until these requirements are independently verified (Gate H / VERIFICATION.md).

**How to use.** When starting a feature, check `blocks_features` below. If this item is still open, either complete the remediation first or stop and escalate. After each correction, run regression (`uv run pytest -q` and the relevant Compose smoke).

Status vocabulary matches the hand-off: Decided · Specified · Implemented · Tested · Verified.

---

## Priority table

The optional OpenSandbox public-tool backend, host-side Credential Vault
provisioning, network/resource containment, lifecycle cleanup, and retry
persistence are tracked in [ADR-018](adr/0018-research-execution-boundary.md).
Local live checks and setup instructions are in [sandbox research](sandbox-research.md).
This work does not close the independent application release gates below.

| ID | Priority | Issue | When to address | Status |
| --- | --- | --- | --- | --- |
| REM-P0-01 | P0 | Private-document access controls and external AI transmission restrictions (D1) | Before private-document processing / Level 3 model steps | Specified · `PolicyEnforcedProvider.client_for` sole path; no silent OpenAI |
| REM-P0-02 | P0 | Workspace isolation and evidence provenance | Before features that depend on multi-tenant evidence, search, or vectors | Tested (live) · `scripts/smoke_rls_two_firm.py`; Gate H Verified still open |
| REM-P1-01 | P1 | Object storage provider (B1 / ADR-017) | Before storage integration becomes deeply coupled | **Decided** SeaweedFS; port 8333 published; smoke `scripts/smoke_b1_seaweed.py` |
| REM-P1-02 | P1 | OCR fixture reproducibility (D4) | Before relying on OCR product test results | Spec harness exists; product path not wired |
| REM-P1-03 | P1 | Six documentation errata (E1–E6) | Next documentation sync | Documented in hand-off README; not yet mirrored into living docs |
| REM-P1-04 | P1 | OFAC source verification (B3) | Before sanctions screening implementation | **Implemented** treas.gov allowlist + fixture fallback + potential-match API |
| REM-P1-05 | P1 | Local-model deployment contract (B4 / D1 local route) | Before enabling private-document AI analysis | Stub profile; private never silent-OpenAI; `/v1/models` probe required |
| REM-P1-06 | P1 | Dependency and asset licence audit (D5 / B5) | Before public distribution | Licence gate CI + CONTRIBUTING/SECURITY; full pin audit open |
| REM-P2-01 | P2 | D6 live false-claims website (B2) | Before final research verification and release | **Decided** ci-local `d6-fixture` nginx; public Pages optional/not required |

---

## Item detail

### REM-P0-01 — D1 private data / external AI

- **Canonical:** master plan › Approved decisions › D1; contracts › `PolicyEnforcedProvider`, `ModelRequestEnvelope`
- **Blocks:** Stage 6 data-room model steps, private embeddings, Level 3 report drafting via external models
- **Done when:** D1-01…D1-12 Tested in `environment: real` (or decision-allowed env); only `PolicyEnforcedProvider` constructs model clients; default deny for private segments
- **Current drift:** Public screening uses `PolicyEnforcedProvider.client_for` → OpenAI when `OPENAI_API_KEY` is set. Private segments still default-deny; no silent OpenAI fallback for private data.

### REM-P0-02 — Workspace isolation and provenance

- **Canonical:** master plan › Tenant authorization (P1-09); provenance / EvidenceSpan; RLS on `firm_id`
- **Blocks:** Stage 4 evidence store sharing, Stage 5 cross-assessment research, Stage 6 private spans
- **Done when:** RLS + `TenantContext` on every repository path; provenance hashes checked; isolation tests with two firms
- **Current drift:** Stage 2 tables have `firm_id` but no RLS yet; seed uses `frm_demo` only.

### REM-P1-01 — Object store (B1)

- **Blocks:** Deep coupling of bucket layout, SSE, versioning assumptions in workers
- **Done when:** SeaweedFS decided; S3 compatibility smoke recorded
- **Decision (2026-11-08):** SeaweedFS + published `:8333`; `scripts/smoke_b1_seaweed.py` green. Keep S3 abstraction; do not hard-code Seaweed APIs.

### REM-P1-02 — OCR fixtures (D4)

- **Blocks:** Declaring D4 product tests Verified
- **Done when:** `fixtures/d4-ocr` carried unchanged; HAR-D4 thresholds enforced in product pipeline tests
- **Current drift:** `worker-docs` `/ocr` + Temporal `DocumentIngestionWorkflow` on `q.docs` (upload queues parse). `scripts/smoke_d4_product.py` exercises product `/ocr`. Flip `OCR_PRODUCT_VERIFIED` only after smoke is green; `ocr_verified` stays false by default.

### REM-P1-03 — Errata E1–E6

- **Blocks:** Doc/spec drift during reviews
- **Done when:** Living `docs/` and compose match errata resolutions (no `/api/v1/test/*`, `frm_demo`, etc.)
- **Current drift:** Hand-off README listed resolutions; living docs are `docs/domain-specification.md` + ADRs.

### REM-P1-04 — OFAC host (B3)

- **Blocks:** Stage 5/6 `sanctions_check` live ingest
- **Done when:** D3-02 confirms `SDN.XML` host; ingest workflow pins hash/XSD
- **Decision (2026-11-08):** Allowlist `*.treas.gov` / treasury.gov only; fixture fallback for CI; potential-match API only (`auto_sanctioned: false`).

### REM-P1-05 — Local LLM profile (B4)

- **Blocks:** Private AI analysis without external transmission
- **Done when:** `--profile local-llm` documented and PolicyEnforcedProvider can route `local`
- **Decision (2026-11-08):** http-echo stub is not a verified route; private path fail-closed with no silent OpenAI fallback.

### REM-P1-06 — Licence gate (D5 / B5)

- **Blocks:** Stage 9 public release
- **Done when:** Apache-2.0 LICENSE, NOTICE, reuse/SPDX gate green; “verify at pin” deps audited

### REM-P2-01 — D6 Pages site (B2)

- **Blocks:** D6-04, D6-05, final research verification
- **Decision (2026-11-08):** Acceptance = compose `d6-fixture` (ci-local nginx at `:8090`), byte-identical to `fixtures/d6-site/false-claims/`. Public Pages optional and not required. Never invent a Pages URL.

---

## Research-agent integration (2026-11-08)

P0 foundations (identity resolution, lineage checks, contradiction records, sufficiency decisions, VoI planner, SearXNG normalize/cache/degrade) live under `thesis_contracts.research` and `thesis_api.services.*`.

Existing REM-* items below remain release gates and are not discarded.

## Stage 4–5 remediation gate status (2026-11-08)

Statuses: **not started · in progress · blocked · implemented · tested · verified**

| Gate | Status | Evidence |
| --- | --- | --- |
| **B1 SeaweedFS** | tested (local) | ADR-017 SeaweedFS decided. Compose publishes `:8333`; creds `any`/`any`. `scripts/smoke_b1_seaweed.py`. Abstraction retained (no Seaweed-native APIs). |
| **D6 false-claims site** | tested (ci-local) | **Decision:** acceptance path is compose `d6-fixture` → `http://localhost:8090` (byte-identical to `fixtures/d6-site/false-claims/`). Public Pages **not required**. Never invent a Pages URL. Harness: `evaluate_d6_live_local` + `scripts/smoke_d6_local.py`. |
| **OCR product path** | tested (health) | Compose `worker-docs` (Tesseract eng) + `/health`; D4 harness still in `fixtures/d4-ocr`. Full Temporal `q.docs` parse/OCR Verified still open. |
| **OFAC** | tested (fixture) | `thesis_api.services.sanctions.ofac` — treas.gov host allowlist, SHA-256, synthetic fixture fallback, potential-match bands, `/api/v1/sanctions/*`. Copy never auto-says "sanctioned". Live SDN download opportunistic. |
| **Local LLM** | tested (deny path) | `--profile local-llm` stub does **not** flip `local_route_available` (requires OpenAI-compatible `/v1/models`). `private_complete` / gateway tests prove no silent OpenAI fallback. |
| **Licence audit** | in progress | Root `LICENSE`/`NOTICE` + `scripts/licence_gate.py` in CI. Full dependency/image/weights/OCR/fixture SPDX audit still open (REM-P1-06). SearXNG AGPL remains a separate Compose service. |
| **RLS / retention** | tested (live + dry-run) | RLS policies + `thesis_app` role. Live two-firm claim isolation: `scripts/smoke_rls_two_firm.py` / `tests/test_two_firm_rls_live.py`. Retention `list→DeletionCertificate` dry-run default; destructive only with `RETENTION_DESTRUCTIVE_DELETE=true`. Object-store delete loop still open. Gate H independent re-run still required for Verified. |

### Owner-free industry decisions (2026-11-08)

No further owner prompts required for these rem items:

1. **B1** — SeaweedFS is the object store; publish S3 port in dev compose.
2. **D6** — ci-local nginx fixture is the acceptance criterion; skip public Pages.
3. **OFAC** — official `*.treas.gov` only; CI uses `fixtures/ofac/synthetic-sdn.xml`; matches are potential-only.
4. **Local LLM** — fail closed for private; stub echo is not a verified route.
5. **Retention** — dry-run certificates by default; never destructive in default env.

**Still not production-ready:** Full OCR/`q.docs` Verified, full licence pin audit, two-firm isolation **Verified** (Gate H), Gate H. ClamAV + worker-docs **in compose**; uploads ClamAV-gated. Local Gate J + RLS via `scripts/run_finish_line.py`.

### Stage 4–5 feature status (honest)

| Slice | Status | Notes |
| --- | --- | --- |
| Evidence snapshot/span persist (`evidence_store`) | implemented · unit tested | Wired before claim insert in screening; offline stub when SafeFetch fails |
| SafeFetch + corroboration in screening | implemented · local E2E | SearXNG when healthy + company-site/heuristics (e.g. sondermind.com); `example.com` last resort only |
| Contradictions emit + resolve UI | implemented · local | Company domain opens contested pair; UI posts `expected_version` → 409 on stale |
| Provenance/SSE sanitize / FET-06 product | partial | Unit lineage + progress allowlist; full FET-06 extractor pin + two-firm DB isolation still open |
| Full Temporal E2E / Gate J | not verified | Live smoke ≠ directive-complete E2E |

**Stages 4–5 feature work does not close these gates.** Production-ready remains forbidden while any release-blocking gate is unresolved.

## Release gate

Production-ready / VERIFIED requires:

1. All P0 items Tested (and Verified under Gate H where release-blocking)
2. P1 items closed or explicitly waived by owner with ADR
3. P2 D6 either Verified or recorded BLOCKED with owner acknowledgment
4. Full pass of applicable `VERIFICATION.md` Parts with evidence records
