# Open-Source VC Due Diligence Agent: hand-off package

Package date: 2026-11-07. Product working name in the UI: **Thesis**.

This package is a **specification, design prototype and seed data set**. It contains no application code. Nothing in it has been implemented, built, deployed or tested as a product. The only things that ran are three specification harnesses (listed under "What actually ran"), and they test the spec artefacts, not the product.

Your job: build the system described in `docs/`, then prove it with `VERIFICATION.md`.

## Contents

| Path | What it is |
| --- | --- |
| `README_FOR_AGENT.md` | This file: reading order, rules, status vocabulary, blockers, errata |
| `VERIFICATION.md` | End-of-implementation acceptance guide with commands, pass criteria and sign-off tables |
| `docs/master-plan.md` | Architecture, agents, workflows, levels, gates, data room, financials, report, API, events, deployment, **Approved decisions D1–D6**, blockers, testing gates, build stages |
| `docs/agent-and-tool-contracts.md` | Pydantic models, tool envelope, permissions, error taxonomy, DD contracts, D1–D4 security types |
| `docs/domain-specification.md` | The twelve diligence domains: inputs, sources, tools, claim schemas, verification, gates, tests |
| `docs/provider-and-tool-matrix.md` | Every provider, library and source with default, credentials, licence, limits, failure behaviour |
| `docs/testing-and-acceptance.md` | Every test ID (SXG, FET, BRW, GH, RSS, EDG, PDF, LLM, OPT, CMP, DEMO, PRV, DD, REAL, FIX, D1–D6) with status |
| `docs/gap-remediation.md` | Gaps G1–G12 and risks R1–R12 with corrective requirements |
| `docs/change-log.md` | History of decisions, contradictions resolved, terminology map, decision log |
| `docs/thesis-ui.md` | UI implementation prompt: stack, design system, screens, action and event contracts, D1–D6 in the UI |
| `prototype/Main.dc.html` | Clickable design prototype of the investor app (props: `mode`, `level`, `viewer`, `externalAI`, `theme`). A visual reference only; it is not the implementation and its data is fixture data |
| `prototype/Console.dc.html` | Clickable prototype of the operator console |
| `prototype/canvas.json` | Board layout for the two prototypes |
| `fixtures/models.py`, `fixtures/build_fixtures.py`, `fixtures/dd/` | Seed set for the demo workspace in backend wire format, validated against a Pydantic transcription of the contracts |
| `fixtures/d4-ocr/` | D4 OCR harness, 11 deterministic PDF fixtures, manifest, tests, recorded results |
| `fixtures/d6-site/` | D6 synthetic false-claims site (`d6-false-claims@1.0.0`), builder, self-checks, recorded results |
| `verify/repo_static_checks.sh` | Static checks the reviewer runs against your finished repository |
| `verify/run_spec_harnesses.sh` | Re-runs the three spec harnesses in this package |
| `verify/evidence_record.template.json` | Shape of one evidence record per test ID |
| `MANIFEST.sha256` | SHA-256 of every file in the package (`sha256sum -c MANIFEST.sha256`) |

Live copies (may be newer than this package): plan doc https://claude.ai/artifact/Qwqmg6f2E3jvmmUMUkvnRh · UI prompt https://claude.ai/artifact/6WN8xbxht3tUoCurYXiavU · prototype https://claude.ai/artifact/SYEkyrgVFzcZunrjZWyF6A. If they differ from this package, ask the owner which is canonical before building.

## Reading order

1. This file, including **Errata** below.
2. `docs/master-plan.md`: Overview → Diligence levels → Approved decisions D1–D6 → Real integrations and the demo workspace → Deployment and first run → Build sequence and ownership. Then the rest.
3. `docs/agent-and-tool-contracts.md` and `docs/domain-specification.md`.
4. `docs/provider-and-tool-matrix.md`.
5. `docs/thesis-ui.md`, with the prototype open beside it.
6. `docs/testing-and-acceptance.md` and `VERIFICATION.md`. Read them **before** writing code: they define what "done" means.
7. `docs/gap-remediation.md` and `docs/change-log.md` for history and rationale.

## Which source wins

| Area | Canonical source |
| --- | --- |
| Architecture, workflows, levels, gates, data room, financial formulas, report, endpoints, events, Compose, D1–D6 | `docs/master-plan.md` |
| Typed models, tools, permissions, error codes | `docs/agent-and-tool-contracts.md` |
| The twelve domains | `docs/domain-specification.md` |
| Libraries, providers, credentials, licences | `docs/provider-and-tool-matrix.md` |
| Test criteria and status | `docs/testing-and-acceptance.md` |
| UI screens, actions, copy | `docs/thesis-ui.md` (defers to master plan for event payloads) |

Precedence when two passages conflict: **Approved decisions D1–D6** > **Real integrations and the demo workspace** > later change-log entries > earlier text. Older change-log entries (for example the audit answers that mention `DEMO_MODE` and `fixture-web` in the default stack) are history and are superseded. If a conflict is not covered by this rule or the errata, stop and ask; do not pick the convenient reading.

## Rules that stay in force

Copied from the owner's instructions. They apply to code, tests, docs, commit messages and reports.

**Data and honesty**

- Private materials must never be searched, disclosed, or used outside the authorized workspace.
- Do not invent financial metrics, legal conclusions, customer data, or other non-public information when source documents are unavailable.
- Never let the LLM silently invent numbers or substitute unsupported estimates for reported financial results.
- The agent identifies issues, inconsistencies and follow-up questions, but must not present its outputs as professional legal, accounting or security certification.
- Never fabricate test results, screenshots, command outputs or successful executions.
- Do not claim to have implemented or tested functionality when the task only updated documentation.
- Never mark a feature complete based solely on a successful mock test. Distinguish tests that actually ran from tests that are merely specified.
- Do not mark a decision implemented simply because documentation has been updated.
- Do not claim that GitHub Pages was created, that a URL is accessible, or that a live test passed without performing those actions and recording evidence. If the project-controlled domain is not deployed, keep D6 at **Pending deployment and verification**. Do not invent a domain. Do not use an unrelated public website to satisfy D6.

**Real integrations**

- The implementation uses real integrations, not mocks. Demo data lives in the database (`frm_demo`, loaded by `seed-demo` through the application services) and reaches the UI through the real API and SSE stream. No MSW, no `DEMO_MODE`, no fake provider in shipped code.
- `docker compose up --build` must start SearXNG automatically, and SearXNG must be tested for actual search results (canary), not only container health.
- A missing OpenAI API key must not prevent the UI from loading.

**Providers, cost and security**

- Do not introduce a mandatory third-party search account. Optional paid search providers stay opt-in.
- Do not embed a live OpenAI API key in source code, containers, browser bundles, logs or test fixtures.
- Do not bypass authentication, paywalls, CAPTCHAs or access controls. Never implement CAPTCHA evasion, proxy rotation to bypass restrictions, or stealth scraping.

**Licensing and content**

- Project licence is Apache-2.0 (D5). If a dependency creates a licensing conflict, report it and propose a compatible replacement rather than silently changing the project licence.
- Do not copy proprietary third-party content into public test fixtures without permission.

**Scope and escalation**

- Do not discard existing requirements because they are not repeated in a later prompt.
- Escalate only decisions that materially affect security, legal obligations, licensing, cost or core product scope. Decide everything else yourself and record it in an ADR.

## Status vocabulary

Use exactly these words in the tracker and in reports.

| Status | Meaning | Evidence required |
| --- | --- | --- |
| Decided | Owner approved the decision | Decision log entry |
| Specified | Behaviour, contracts and tests are written down | Doc section and test IDs |
| Implemented | Code merged | Commit SHA, file list |
| Tested | The test IDs ran and passed in `environment: real` (or `ci-local` where a decision allows it, e.g. D3-05, D4-12, D6-01..03) | CI job link or captured log per test ID |
| Verified | An independent reviewer reran the commands on a clean checkout and got the same result (Gate H) | Reviewer name, date, commit SHA, logs |

Test environments: `real` = full Compose stack with real services, real OpenAI (cost-capped key), real SearXNG and real public sources. `ci-local` = deterministic local fixtures where a decision explicitly permits it. `unit` = test doubles; never counts toward Tested or Verified.

Current status of every decision: **D1–D5 Decided · Specified. D6 Decided · Specified · Pending deployment and verification.** D4 also has a passing harness, which is not product evidence.

## What actually ran (2026-11-07)

| Run | What | Result | Evidence in package |
| --- | --- | --- | --- |
| FIX-01 | Seed data validated against the contracts | 13/13 files, 14/14 events, 7/7 negative cases rejected | `fixtures/build_fixtures.py` output |
| HAR-D4 | Native-first extraction with page-level Tesseract fallback on 11 fixtures | 12/12 passed (Tesseract 5.3.4, pypdf 6.17.0, pypdfium2 5.15.1). Character error rate 0.0 on clean scans, page confidence 95.4–95.8, about 0.65 s per page | `fixtures/d4-ocr/results.txt` |
| SITE-D6 | D6 fixture site self-checks | 7/7 passed | `fixtures/d6-site/results.txt` |

All three were re-run from this package's own folder layout before zipping and passed again. Everything else in `docs/testing-and-acceptance.md` is NOT_RUN.

## Blockers that need a human

| ID | Blocker | What to do |
| --- | --- | --- |
| B1 | MinIO's upstream repository was archived on 2026-04-25 and no longer publishes official images | Keep the S3 abstraction. Owner must choose the default store; the recommendation is SeaweedFS (Apache-2.0) after an S3 compatibility run (versioning, lifecycle, SSE, multipart). Do not switch silently |
| B2 | D6 repository and GitHub Pages site do not exist | Needs owner authorization to create a public repo (candidate `jmpumuro/vc-dd-test-fixtures`) and publish `fixtures/d6-site/false-claims/` unchanged. Until then D6-04 and D6-05 stay BLOCKED |
| B3 | OFAC `SDN.XML` host (V-D3-1) | Confirm `SDN.XML` is served from `sanctionslistservice.ofac.treas.gov` exports before release (D3-02) |
| B4 | No local model shipped for D1 | Provide `--profile local-llm`; each deploying firm picks its model. Without it, Level 3 model steps on private data are skipped by default, which is correct behaviour |
| B5 | Licences marked "verify at pin" (trafilatura, python-docx, anyascii, rapidfuzz, others in the matrix) | Run the licence gate at first build; report conflicts per the licensing rule |

## Errata found while packaging

These are wording conflicts left in the docs. Apply the resolution given here; it follows the precedence rule above.

| ID | Where | Conflict | Resolution |
| --- | --- | --- | --- |
| E1 | Master plan › Testing gates per agent, "Test hooks" paragraph | Describes `/api/v1/test/*` routes under `APP_ENV=test`, while "Real integrations and the demo workspace" and the change log say there are no event-injection endpoints and the hooks were removed | No `/api/v1/test/*` routes. Faults come from Toxiproxy, `docker compose stop` and SIGKILL, as the same section's preceding paragraph says. `verify/repo_static_checks.sh` fails if the routes exist |
| E2 | Master plan › Testing gates, Gate C row | "Real PostgreSQL, MinIO, Temporal and a local fixture web server" | Gate C uses real services and real public sources. The local fixture server exists only for D6 `ci-local` runs under `--profile test` |
| E3 | Master plan › Deployment, "Sample workspace" (`frm_sample`) and "CI … drives the browser journey against fixtures" | Predates the real-integration change; overlaps `frm_demo` | `frm_demo` is the demo and the UI test workspace. If you keep `frm_sample`, it must be seeded through the application services like `frm_demo` and be read-only. Browser journeys run against the real API with `frm_demo` seeded |
| E4 | `fixtures/build_fixtures.py` | Uses firm id `frm_dev`; the plan's demo firm is `frm_demo` | `seed-demo` writes the seed set into `frm_demo`. Treat `frm_dev` in fixture files as a placeholder to remap |
| E5 | Master plan › Real-time events and UI endpoints, row for `PUT /workspace/external-ai-policy` | Description still says "Owner accepts the provider data-processing terms for Level 3" | D1 governs: Level 3 needs no acceptance to start; the policy is off by default and authorizes categories and purposes per workspace |
| E6 | `prototype/` | The prototype is a clickable mock with fixture data | It is a visual reference only. Do not port its data or its in-page state into the app |

## How to report

Follow the master plan's delegation protocol and tracker format (`implementation-tracker.json`). For every stage report: changed files, migrations, tests added, commands run with actual output, risks, integration impact. One evidence record per test ID (`verify/evidence_record.template.json`). If you could not run something, say so and give the reason; never fill a result field without an artifact.
