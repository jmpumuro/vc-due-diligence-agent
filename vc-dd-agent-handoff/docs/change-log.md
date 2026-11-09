# Correction report

The provider and tool audit found 26 issues; all are corrected in this doc (status DOC\_UPDATED). None is VERIFIED, because no repository exists and no test has run. Six decisions remain open for the maintainer.

**Scope and format.** Reviewed: this plan (which already merges the Gap Remediation Addendum, marked P0-xx and P1-xx), the UI implementation prompt, and the audit brief.

Deliverables were adapted to this workspace:

- The corrected plan is this doc's main tab, not a separate .md file. The addendum has no separate corrected copy, because its content lives in the plan.
- The provider matrix, tool contracts, test matrix and this report are tabs.
- `settings.yml` is specified in Tool contracts, the Compose services in the main tab's Deployment section, and the environment variables below.

## Findings and changes

| ID | Finding | Section changed | Change | Evidence | Status |
| --- | --- | --- | --- | --- | --- |
| C-01 | Default models obsolete: `o4-mini` shut down 23 Oct 2026; `gpt-4.1` and `gpt-4.1-mini` shut down 14 Jan 2027 | Agent specifications | Proposed `gpt-6-luna` and `gpt-5.6-terra`, OpenAI's listed replacements, checked at startup and baselined in the quality harness | [OpenAI deprecations](https://developers.openai.com/api/docs/deprecations) | DOC\_UPDATED; verify with LLM-04 |
| C-02 | "Different model family" for the Critic is unachievable with one provider | Critic Agent | Different model ID from Evaluation, enforced by config validation | Design | DOC\_UPDATED |
| C-03 | `web_search` had no provider | Shared runtime; Tool contracts | SearXNG default; others opt-in | SearXNG docs | DOC\_UPDATED |
| C-04 | SearXNG serves only HTML by default; JSON requests return 403 | Tool contracts | `formats: [html, json]`; health check requires JSON | [Search settings](https://docs.searxng.org/admin/settings/settings_search.html), [search API](https://docs.searxng.org/_sources/dev/search_api.rst.txt) | DOC\_UPDATED; verify with SXG-01 |
| C-05 | SearXNG's limiter needs Valkey; nothing decided | Tool contracts | Limiter off on an internal-only instance, guarded by an exposure check; app-level throttling | [Limiter](https://docs.searxng.org/admin/searx.limiter.html) | DOC\_UPDATED; verify with SXG-09 |
| C-06 | Readiness and real search availability were one check | Deployment; Tool contracts | Separate readiness check and functional canary; `search` block in `/system/status` | Audit requirement | DOC\_UPDATED; verify with SXG-10 |
| C-07 | Playwright shared the fetch worker | Runtime queue table; Compose | `q.browser`, `worker-browser`, egress proxy | Design | DOC\_UPDATED; verify with BRW-01 |
| C-08 | SSRF rules covered only HTTPX | Security | One network policy for every adapter, including browser subresources | Design | DOC\_UPDATED; verify with FET-01 to 03, BRW-01, BRW-04 |
| C-09 | Context ranking implied embeddings were required | Context assembly | Embeddings off by default; full-text ranking | Design | DOC\_UPDATED |
| C-10 | Snippets and syndicated copies could pass as confirmation | Evidence provenance | `source_kind`, `syndication_group`, independent-confirmation rule, search-is-not-evidence rule | Design | DOC\_UPDATED |
| C-11 | Provider failures did not reach coverage, uncertainty or the memo | Domain types; Failure handling | `SourceGap`, raised uncertainty, "Coverage limits" memo line | Design | DOC\_UPDATED; verify with PRV-15 |
| C-12 | "OIDC required elsewhere" implied an external identity service | Deployment; Decisions | Built-in accounts with one-time `/setup`; OIDC optional | Design | DOC\_UPDATED |
| C-13 | Notification and CRM defaults unspecified | Retry safety | In-app notifications; local JSON/CSV export and webhook; others opt-in | Design | DOC\_UPDATED; verify with PRV-19 |
| C-14 | Browser could receive `http://api:8000` | Deployment | `INTERNAL_API_URL` and runtime-injected `PUBLIC_API_URL` | Design | DOC\_UPDATED |
| C-15 | Ports list exposed Temporal gRPC and MinIO API | Deployment | Internal-only list; development-only consoles | Design | DOC\_UPDATED |
| C-16 | PDF library unspecified; AGPL risk | Decisions; Provider matrix | pypdf (BSD-3-Clause); PyMuPDF excluded (AGPL-3.0) | [Comparison](https://pdf.oxide.fyi/docs/comparison/pymupdf-vs-pypdf) (secondary) | DOC\_UPDATED; licence to confirm from package metadata |
| C-17 | EDGAR named as a source with no tool or fair-access rules | Agent table; Tool contracts; Provider matrix | `filings_read`, User-Agent, 5 requests/second | [SEC fair access](https://www.sec.gov/os/accessing-edgar-data) | DOC\_UPDATED; verify with EDG-01 |
| C-18 | Risk of depending on OpenAI-hosted prompts, Evals or Agent Builder | Shared runtime | Prompts versioned in the repository | [OpenAI deprecations](https://developers.openai.com/api/docs/deprecations) (shutdown 30 Nov 2026) | DOC\_UPDATED |
| C-19 | No tool envelope or tool error taxonomy | Tool contracts | Added | Audit requirement | DOC\_UPDATED |
| C-20 | Per-role tool permissions implicit | Tool contracts | Permission matrix; no network for Verification, Evaluation, Critic, Memo | Design | DOC\_UPDATED |
| C-21 | GDELT terms and limits unknown | Provider matrix | PLANNED, not default | [GDELT DOC 2.0](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/) (no terms stated) | DOC\_UPDATED |
| C-22 | Legality of other sources unclassified | Provider matrix | Classification table; LinkedIn prohibited by policy | Audit requirement | DOC\_UPDATED |
| C-23 | SearXNG is AGPL-3.0 while the project licence is unchosen | Decisions | Flagged for the maintainer's licence review | [Repository licence](https://github.com/searxng/searxng) | OPEN |
| C-24 | Search queries reveal deal interest; a shared cache could leak it | Tool contracts | Queries `tenant_private`; tenant-scoped cache keys | Design | DOC\_UPDATED; verify with SXG-08 |
| C-25 | Demo mode would still need internet for search | Deployment | `fixture-web` and offline demo | Design | DOC\_UPDATED; verify with DEMO-01 |
| C-26 | Agent budgets priced on retired models | Agent table | Marked provisional; re-derive from current pricing | Pricing UNVERIFIED | OPEN |

## Answers to the audit's questions

1. **Default engines and degraded behaviour.** The engine set of the pinned SearXNG release, narrowed by an allow-list; the exact default list is UNVERIFIED and must be recorded before Stage 2 closes. When engines block requests, search reports `degraded` with failed engines named, research continues on RSS and direct sources, and coverage records the gap (SXG-02, PRV-04).
2. **Readiness versus availability.** Readiness means the JSON endpoint answers; availability is proven by the hourly canary returning real results (SXG-10).
3. **Fetching cited pages.** `fetch_url` (HTTPX), with `render_page` for JavaScript pages. If neither can fetch, the claim stays unverified and a `SourceGap` is recorded (FET-04, FET-05).
4. **Playwright network safety.** Yes, by design: request interception plus the egress proxy cover navigations, subresources, iframes, WebSockets and downloads (BRW-01, BRW-04).
5. **Zero-credential adapters.** SearXNG, fetch, browser, RSS, GitHub (unauthenticated) and EDGAR (needs only a User-Agent built from the owner's email at `/setup`). Opt-in: OpenAI hosted search, Tavily, Brave, Exa, GDELT, GitHub token, SMTP, Slack, CRM, OIDC, embeddings.
6. **GitHub public access.** Enough for demo (fixtures) and light live use at 60 requests/hour per IP; limits surface as `RATE_LIMITED` with reset time and a visible warning (GH-01, PRV-07).
7. **Libraries and provenance.** HTML: selectolax; PDF: pypdf; RSS and Atom: feedparser; JavaScript pages: Playwright. All produce `SourceSnapshotMeta` with raw and normalized hashes, extractor version, final URL and redirect chain (FET-06).
8. **News discovery.** SearXNG news plus the RSS registry. Duplicate press releases share a `syndication_group` and count once; confirmation needs an independent source.
9. **Failures and the memo.** Gaps raise uncertainty and appear as a "Coverage limits" line (PRV-15).
10. **Offline and live without code changes.** Yes: `DEMO_MODE` swaps providers to fixtures by configuration (DEMO-01).
11. **Billable calls.** Only OpenAI by default; it is reserved against budgets and ledgered. Every other billable provider is opt-in, and billable fallback needs explicit permission (SXG-11, LLM-03).
12. **Services guaranteeing the UI.** See the Deployment table: postgres, temporal-db-setup, temporal, minio and minio-init, searxng, egress-proxy, migrate, api, the workers, worker-browser, fixture-web, web (CMP-01, PRV-01).
13. **Terms that restrict content.** Per-source policy files; LinkedIn and login-only networks prohibited; app stores and third-party job boards unsupported; GDELT pending; publisher licences limit excerpt display and retention.
14. **Adding a provider.** Implement the capability protocol, declare credentials, add a policy file, register it, pass the contract tests (Tool contracts, "Adding a provider").
15. **Proof.** The Provider tests tab maps each answer to a test; all NOT\_RUN.

## Open decisions

- Project licence and its compatibility with running SearXNG (AGPL-3.0) as a separate service.
- Final model IDs after the startup availability check and a quality baseline; budgets from current pricing.
- SearXNG engine allow-list for the pinned release.
- Whether to enable GDELT once its terms and limits are confirmed.
- Contents of the default RSS feed registry.
- Which national company registries to support beyond EDGAR.

## Environment variables (.env.example specification)

`APP_ENV`, `DEMO_MODE`, `OPENAI_API_KEY` (live only), `SEARCH_PROVIDER=searxng`, `SEARXNG_URL=http://searxng:8080`, `GITHUB_TOKEN` (optional), `EDGAR_USER_AGENT` (filled from `/setup` if blank), `BROWSER_ENABLED=true`, `EMBEDDINGS_PROVIDER` (blank = off), `INTERNAL_API_URL`, `PUBLIC_API_URL`, `PUBLIC_WEB_URL`, optional `OIDC_*`, `SMTP_*`, `SLACK_WEBHOOK_URL`, `CRM_*`, `OTEL_EXPORTER_OTLP_ENDPOINT`. No variable needs a third-party signup to start the stack.

## ADRs to write

ADR-010 SearXNG as default search; ADR-011 browser isolation and egress proxy; ADR-012 embeddings optional; ADR-013 built-in authentication; ADR-014 model defaults and startup verification; ADR-015 PDF library and licence policy; ADR-016 public-source classification.

## 2026-11-07 — Upgrade to VC Due Diligence Agent

Documentation only. Nothing in this entry has been implemented, built or tested.

### Canonical sources after this change

| Requirement area | Canonical location |
| --- | --- |
| Architecture, workflows, levels, gates, private documents, financial formulas, checklists, report, endpoints, events, Compose | Master plan |
| Typed models, tools, permissions, error codes | Agent & tool contracts |
| The twelve domains | Domain specification |
| Libraries, providers, credentials, licences | Provider & tool matrix |
| Verification criteria and status of every test | Testing & acceptance |
| Remaining risks and corrective requirements | Gap remediation |
| Decisions, contradictions, open questions | This change log |
| UI screens, actions and events | Thesis UI implementation prompt (separate doc), which defers to the master plan for event payloads |

### Retained

Eight agent roles; sourcing, screening, research, gap-research and monitoring workflows; ledger, atomic budgets, idempotency, outbox; provenance and exact-quote spans; version-bound review and `409 STALE_REVIEW_TARGET`; lifecycle state machine; SafeFetcher, egress proxy, Playwright fallback; SearXNG default with readiness and canary; OpenAI default with startup model verification; built-in auth and `/setup`; readiness modes; `http://localhost:3000` after `docker compose up --build`; UI loads without an OpenAI key; all earlier tests.

### Modified

- Product name: "Open-Source VC Research Agent" → "Open-Source VC Due Diligence Agent". The UI working name "Thesis" is kept.
- Screening workflow is now Level 1 of `DueDiligenceWorkflow`; workflow IDs move from `screen:{firm}:{company}` to `dd:{firm_id}:{assessment_id}:r{revision}`. Legacy IDs remain readable and are not reused.
- Agent contracts extended for domains (planner emits `DomainPlan`s, verification applies domain rules and contradiction analysis, memo writes the 21-section report). No new agents.
- Single investment score split into four measures.
- Memo replaced by the 21-section `ReportVersion`; the old memo maps to sections 1, 14, 19 and 20.
- Vector search: see contradiction C1.
- Compose gains `clamav` and `worker-docs`; queues gain `q.docs`.

### Added

Three diligence levels; twelve domain modules; seven finding classes and sufficiency gates; `DomainResearchWorkflow` children and `DocumentIngestionWorkflow`; evidence freeze; `INFORMATION_REQUESTED` state; upgrade endpoint; data room with ClamAV, sandboxed parsers, envelope encryption, deal teams, private-processing acknowledgement; `ddcalc`; financial validation queue; legal, commercial and security checklists; risk register; contradiction review; information requests; report exports (web, PDF, DOCX, JSON) with schema `ddreport@1`; new tools (`document_lookup`, `table_extract`, `ddcalc`, `checklist_review`, `sanctions_check`, `dns_tls_check`, `github_profile`); DD events, endpoints and error codes; DD-01 to DD-30 tests; gap remediation R1–R12.

### Deferred

- Founder-facing data-room portal (companies upload directly). Uploads are by deal-team members only for now.
- Automatic sending of information requests to companies.
- OCR on by default (kept opt-in) — superseded by D4: local OCR is now an automatic fallback.
- Commercial data providers (Crunchbase, PitchBook, OpenCorporates): opt-in adapters only, not specified in detail.
- Formal accounting reconciliations (GAAP/IFRS adjustments) beyond the stated formulas.

### Terminology map

| Old term | New term |
| --- | --- |
| Research agent (product) | Due diligence agent |
| Screen / screening run | Level 1 assessment |
| Deep research | Level 2 public diligence |
| — | Level 3 enhanced diligence |
| Memo | Due diligence report (`ReportVersion`) |
| Research question | Research question tagged with `domain_id` |
| Score | Attractiveness (one of four measures) |
| Evidence pack | Evidence snapshot set |

### Contradictions resolved

| ID | Contradiction | Resolution |
| --- | --- | --- |
| C1 | The upgrade brief lists pgvector as the default vector search; the earlier provider audit made embeddings optional and off by default | pgvector is installed in every deployment. Embeddings are on in live mode, use fixture vectors in demo mode, and full-text ranking remains the fallback. Private spans are embedded only when the acknowledgement covers embeddings |
| C2 | Earlier docs used `screen:` workflow IDs; revisions need distinct IDs | `dd:{firm}:{assessment}:r{n}`, legacy IDs kept read-only |
| C3 | "Never let the LLM invent numbers" vs LLM-based table extraction | LLM may propose cell values only; tables must pass structural checks or human validation before `ddcalc` uses them |
| C4 | "Do not disclose private materials" vs sending passages to OpenAI | Treated as processing by a provider under an explicit owner acknowledgement; without it Level 3 runs without LLM steps (open decision D1) |
| C5 | Earlier event catalog had no document or domain events | Added to the master plan and the UI prompt with matching names |

### Decision log D1–D6

| ID | Decision | Outcome (2026-11-07) | Status |
| --- | --- | --- | --- |
| D1 | Private document text and external AI | Off by default; owner or admin authorizes provider, categories and purposes; local-model alternative; enforced before every request | Decided · Specified |
| D2 | Data-room retention | 90 days after closure; admins may only shorten; holds and immediate deletion; verified Temporal cleanup | Decided · Specified |
| D3 | Sanctions data source | Official OFAC SDN + consolidated non-SDN; others optional | Decided · Specified |
| D4 | OCR | Local Tesseract as automatic page-level fallback | Decided · Specified · harness passed (not product) |
| D5 | Project licence | Apache-2.0 | Decided · Specified |
| D6 | False-claims test site | Project-controlled GitHub Pages; local fixture in normal CI | Decided · Specified · **Pending deployment and verification** |

Canonical detail for all six: master plan › Approved decisions D1–D6.

### Unresolved questions

- Model IDs (`gpt-6-luna`, `gpt-5.6-terra`, embeddings model) and their prices must be re-verified at implementation time; budgets remain provisional.
- Licences marked "verify at pin" in the matrix have not been checked against the pinned releases.
- Companies House and EDGAR rate limits are stated from published guidance and must be confirmed.
- Whether seccomp profiles are available on every target host (Docker Desktop on macOS and Windows may differ).

**Also decided:** C6, memo names kept as API aliases of the report (`memo_version_id` = `report_version_id`, `assessment.memo_ready` sent with `report.version_created`, `/memo` derived from report sections 1, 14, 19, 20) so the earlier contracts and UI keep working; removal only in a future major API version. **Known gap:** resolved the same day: the design prototype now shows the due diligence screens (levels, domains, 21-section report, data room, financial validation, risks, contradictions, requests, settings) and the console shows domain child workflows, document ingestion, new health rows and per-domain cost. It is a clickable mock with fixture data, not an implementation.

## 2026-11-07 (later) — Gap closure and real integrations

Documentation, prototype and seed data only. No application code exists yet; nothing here claims an implemented or tested feature.

### Gaps closed

| # | Gap | Resolution | Where |
| --- | --- | --- | --- |
| 1 | Review decision lacked `request_information` | Added to `SubmitReviewRequest` with required `requested_items`; ends the revision in `INFORMATION_REQUESTED` and drafts requests | Master plan › review contracts |
| 2 | Three recommendation vocabularies | One `Recommendation = advance \| hold \| pass \| inconclusive` plus `conditions[]`; legacy `watch` → `hold`, `insufficient_evidence` → `inconclusive` (migration 0051) | Contracts › Shared types |
| 3 | Summary view carried one combined score | `AssessmentSummaryView` now has `measures`, `domains[]`, `finding_counts`, `stage`, `conditions`; old fields only under `?compat=research` | Master plan |
| 4 | Progress counted questions | `assessment.progress` reports `stage`, `domains_complete`, `domains_total`, documents | Master plan › Progress and stages |
| 5 | Console invented states | States unchanged; finer steps are `stage` values shown as `STATE · stage` | Master plan, prototype console |
| 6 | No domain configuration API | `GET`/`PUT /config/domains`, `422 DOMAIN_REQUIRED`, new config version per change | Master plan, UI prompt |
| 7 | UI prompt stale | File tree, components, screens, field mapping, decisions, settings and stages updated | UI prompt |
| 8 | No backend-format sample data | Seed set `project/fixtures/dd/` (13 files + events) validated against the contracts (FIX-01) | Prototype files, Testing |
| 9 | Validation wait unspecified | Non-blocking by default (report proceeds, metrics not computable, validation starts a new revision); optional blocking mode with reminders, escalation and 7-day timeout | Master plan |
| — | Supporting types undefined | `PeriodRange`, `InputRef`, locators, `FinancialCell/Row`, `TableCheck`, `Correction`, `ScorecardRow`, `OverrideCondition`, `DomainConfigSet`, `AssessmentState` | Contracts › Supporting types |
| — | Domain gate used `inconclusive` | Gate values aligned with `GateResult`; `inconclusive` is only a recommendation | Master plan |

### Data errors found by validating the seed set

- September MRR movements in the prototype did not roll forward to the stated total (52,750 + 4,800 + 1,600 − 1,300 ≠ 53,350). Corrected to 2,100 / 600 / −2,100.
- Per-domain finding counts summed to 70 while the headline said 76. Domain counts corrected.
- Revenue growth shown as 182%; the traced inputs give 181.5%.

### Real integrations (requested by the user)

- **Removed from the runtime:** `DEMO_MODE`, `FakeLLMProvider` in workers, `fixture-web` in the default stack, browser-side MSW, `/api/v1/test/*` hooks.
- **Added:**
  - the demo workspace `frm_demo`, loaded by `seed-demo` through the application services;
  - demo documents ingested by the real ClamAV and parser pipeline, and calculations computed by `ddcalc` at seed time;
  - the event history written through the outbox and served by the real SSE stream;
  - seeded demo users signing in via `POST /auth/demo-session` with normal sessions;
  - `POST /demo/reset` and `DEMO_WORKSPACE=false`.
- **Renamed:** "Rerun on fixtures" is now "Replay from ledger", an operator-only tool on `q.replay` (`--profile ops`) that never feeds the demo or acceptance. Error `FIXTURES_UNAVAILABLE` is now `REPLAY_UNAVAILABLE`.
- **Tests:**
  - every acceptance test runs against the real stack: real OpenAI with a cost-capped CI secret, real SearXNG and real public sources;
  - faults come from Toxiproxy, stopped containers and killed workers;
  - unit tests with doubles are labelled `unit` and never mark a feature complete;
  - new rows REAL-01 to REAL-10.
- **Decision taken under the escalation rule:** the false-claims test site (DD-17) must be a real domain controlled by the project. Which domain to use was an open item (D6); now decided as project-controlled GitHub Pages, deployment pending (see Decision log D1–D6).

## 2026-11-07 (evening) — Decisions D1–D6 incorporated

Documentation updated. No product code exists, so nothing is Implemented, Tested or Verified. Harness and fixture runs listed below are real executions that test specification artifacts only.

### Files modified

| Document › tab | Changes |
| --- | --- |
| Plan › Master plan | New section "Approved decisions D1–D6" (decision, rationale, configuration, components, requirements, security, failure behaviour, tests, acceptance, status for each), remaining blockers B1–B5. Replaced old defaults: Level 3 prerequisite, upload authorization, embeddings, model processing, retention, OCR, licence rows, endpoints and error codes |
| Plan › Agent & tool contracts | `DocumentSpan` OCR provenance; sanctions tool; private-data enforcement rule; error code; new section "Security and data-handling contracts" (`ModelRequestEnvelope`, `PolicyDecision`, `ExternalTransmission`, `RetentionExtension`, `LegalHold`, `DeletionCertificate`, `OcrPageResult`) |
| Plan › Domain specification | Legal domain sources, tool, criticality and tests for D3; shared rule for D1, D2, D4 |
| Plan › Provider & tool matrix | OCR and sanctions rows rewritten; selectolax lexbor note; new rows for D1, D2, D3, D5, D6 and blocker B1 |
| Plan › Testing & acceptance | D1-01 to D6-05; DD-05 updated; executed runs table |
| Plan › Gap remediation | R1 resolved by D1; R3 adds local OCR |
| Plan › Change log | Decision log statuses; this entry |
| UI implementation prompt | Settings, Level 3, retention, sanctions review and OCR provenance screens, actions, events and copy |
| Design prototype | Settings page (external AI policy, retention 90 days), Level 3 picker reason, sanctions health row, console health; D4 and D6 fixtures added under `project/fixtures/` |

### Contradictions resolved

| Was | Now |
| --- | --- |
| Level 3 required a private-processing acknowledgement, after which excerpts went to OpenAI | Level 3 starts without consent; external processing off by default; local model or explicit per-category authorization (D1) |
| `409 PRIVATE_PROCESSING_NOT_ACCEPTED` | `403 EXTERNAL_AI_NOT_AUTHORIZED` |
| Retention firm-set, default 180 days, or "until the data room is deleted" | 90 days after closure, shorten only, holds, verified deletion (D2). Public snapshot purge (180 days) is unchanged and separate |
| Sanctions: OFAC, EU and UK lists by default | OFAC SDN + consolidated by default; EU, UK, UN optional (D3) |
| OCR off by default; scanned pages flagged "image only" | Automatic local fallback; image uploads now accepted (D4) |
| Licence chosen by maintainer; python-docx "UNVERIFIED" | Apache-2.0 with licence gate (D5) |
| "Only real results count" vs D6's "deterministic local fixtures for normal CI" | Normal CI may run `ci-local` fixtures (served by `fixture-web` under `--profile test`); Tested and Verified still require `real` runs, and D6 requires the live job |
| D6 test site listed as an open item | Concrete hosting and testing contract; deployment pending |

### New implementation requirements (summary)

- D1: `PolicyEnforcedProvider`, segment tagging, egress guard, payload codec, local model profile and probe, policy API, audit table.
- D2: retention records, scheduler and deletion workflows, holds, extension, verification, certificate, backup and key-rotation policy.
- D3: ingest workflow, XSD validation, dataset versions, normalization, matching, review queue, wording lint.
- D4: page classifier with the refined garbled-text rule, pypdfium2 rendering, Tesseract, provenance fields, limits, image uploads.
- D5: LICENSE, NOTICE, SPDX headers, manifests, licence gate, provenance file, DCO.
- D6: fixtures repository, Pages deployment, `fixture-web` test profile, live preflight and verification record.

### Findings made while doing this work

- A printable-character check misses broken PDF font maps, which extract as "■" glyphs. The D4 rule now uses a garbage-character ratio and a word ratio.
- selectolax 1.0 rejects the old Modest backend with an ImportError; use `selectolax.lexbor`.
- OFAC's SDN page links exports on a different host from the consolidated page (V-D3-1).
- MinIO's upstream repository is archived and no longer publishes official images (B1).

### Decisions requiring human authorization

1. B2 / D6: authorize creating a public repository `vc-dd-test-fixtures` under `jmpumuro`, or name the organization that should own it.
2. B1: choose the object-store default (SeaweedFS recommended) now that MinIO is archived.
3. Per deployment, not a project decision: which local model, if any, a firm runs for D1.
