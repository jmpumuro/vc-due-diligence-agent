# Provider tests

Every provider and tool test, with the command to run and its gate. **All results are NOT\_RUN**: no repository exists yet. Commands are proposals to be fixed when the test files are created. Live tests run only with `LIVE_TESTS=1` and the named credentials, never in default CI.

| ID | Provider | Case | Level | Proposed command | Gate | Result |
| --- | --- | --- | --- | --- | --- | --- |
| SXG-01 | SearXNG | `formats` without `json` → `SEARCH_UNAVAILABLE` with a "json not enabled" diagnostic; no fallback | Integration | `pytest tests/providers/searxng -k json_disabled -m integration` | C | NOT\_RUN |
| SXG-02 | SearXNG | All upstream engines suspended → `SEARCH_DEGRADED`; empty results flagged, never "no presence" | Integration | `pytest tests/providers/searxng -k engines_blocked` | C | NOT\_RUN |
| SXG-03 | SearXNG | Tracking parameters, ports, fragments, case and IDNA normalized; duplicates merged with engine list | Unit, property-based | `pytest tests/providers/searxng/test_normalize.py` | B | NOT\_RUN |
| SXG-04 | SearXNG | Timeout → 2 retries with jitter, then `TIMEOUT` | Unit | `pytest tests/providers/searxng -k timeout` | B | NOT\_RUN |
| SXG-05 | SearXNG | Malformed JSON → `INVALID_RESPONSE` | Unit | `pytest tests/providers/searxng -k malformed` | B | NOT\_RUN |
| SXG-06 | SearXNG | Injection text in titles and snippets never reaches instructions; tool calls unchanged | Security | `pytest tests/security/test_search_injection.py` | E | NOT\_RUN |
| SXG-07 | SearXNG | 50 parallel queries respect the token bucket and 4-query cap | Integration | `pytest tests/providers/searxng -k concurrency` | C, D | NOT\_RUN |
| SXG-08 | SearXNG | Cache TTLs honoured; keys include `firm_id`; tenant B never gets tenant A's cached query | Integration, security | `pytest tests/providers/searxng -k cache` | C, E | NOT\_RUN |
| SXG-09 | SearXNG | No host port published; startup fails if one is mapped while `limiter: false` | Infrastructure | `docker compose config \| python scripts/check_searxng_exposure.py` | I | NOT\_RUN |
| SXG-10 | SearXNG | Readiness passes while canary fails → status `degraded`, not `ok` | Integration | `pytest tests/providers/searxng -k canary` | C | NOT\_RUN |
| SXG-11 | Config | Default configuration contains no paid search provider or key | Contract | `pytest tests/config -k no_paid_search` | A | NOT\_RUN |
| FET-01 | SafeFetcher | SSRF corpus blocked: localhost, 169.254.169.254, `::1`, IPv4-mapped IPv6, decimal and octal IPs, IDNA tricks, userinfo, odd ports | Security | `pytest tests/security/test_ssrf.py` | E | NOT\_RUN |
| FET-02 | SafeFetcher | Redirect to a private IP and simulated DNS rebinding blocked | Security | `pytest tests/security/test_ssrf.py -k "redirect or rebinding"` | E | NOT\_RUN |
| FET-03 | SafeFetcher | Oversized body and gzip bomb stopped while streaming | Security | `pytest tests/security/test_limits.py` | E | NOT\_RUN |
| FET-04 | SafeFetcher | robots or policy block → `SOURCE_BLOCKED` with reason; no retry | Integration | `pytest tests/providers/fetch -k blocked` | C | NOT\_RUN |
| FET-05 | SafeFetcher | 403, 404 and 429 mapped correctly; 404 never treated as "no evidence exists" | Unit | `pytest tests/providers/fetch -k status_mapping` | B | NOT\_RUN |
| FET-06 | Extraction | Normalized text, hashes and span offsets reproduce exactly for a pinned extractor version | Unit | `pytest tests/provenance -k reproducible` | B | NOT\_RUN |
| BRW-01 | Browser | Subresource to a metadata endpoint blocked by interception and egress proxy | Security | `pytest tests/security/test_browser_ssrf.py` | E | NOT\_RUN |
| BRW-02 | Browser | JavaScript-only fixture page rendered and snapshotted | Integration | `pytest tests/providers/browser -k js_only` | C | NOT\_RUN |
| BRW-03 | Browser | Crash or hang → `BROWSER_FAILED`; context cleaned up; other branches finish | Workflow | `pytest tests/workflows -k browser_failure` | D | NOT\_RUN |
| BRW-04 | Browser | Downloads, WebSockets and service workers blocked | Security | `pytest tests/security/test_browser_ssrf.py -k "download or websocket"` | E | NOT\_RUN |
| GH-01 | GitHub | `x-ratelimit-remaining: 0` → wait until reset; partial evidence and warning | Unit | `pytest tests/providers/github -k primary_limit` | B | NOT\_RUN |
| GH-02 | GitHub | Secondary limit with and without `retry-after` | Unit | `pytest tests/providers/github -k secondary_limit` | B | NOT\_RUN |
| GH-03 | GitHub | 404 versus private or forbidden distinguished | Unit | `pytest tests/providers/github -k not_found` | B | NOT\_RUN |
| GH-04 | GitHub | ETag conditional request returns `not_modified` | Integration (fixture) | `pytest tests/providers/github -k etag` | C | NOT\_RUN |
| GH-05 | GitHub | Live smoke, unauthenticated | Live, opt-in | `LIVE_TESTS=1 pytest -m live_github` | — | NOT\_RUN |
| RSS-01 | Feeds | Malformed feed → `PARSER_FAILED`; other feeds continue | Unit | `pytest tests/providers/feeds -k malformed` | B | NOT\_RUN |
| RSS-02 | Feeds | ETag and Last-Modified honoured | Integration | `pytest tests/providers/feeds -k conditional` | C | NOT\_RUN |
| RSS-03 | Feeds | Duplicate GUIDs merged; edited items versioned; deleted items marked | Unit | `pytest tests/providers/feeds -k dedupe` | B | NOT\_RUN |
| EDG-01 | EDGAR | User-Agent header present; throttle at or below 5 requests/second | Unit | `pytest tests/providers/edgar` | B | NOT\_RUN |
| PDF-01 | PDF | Malformed and oversized PDFs fail safely within caps | Security | `pytest tests/security/test_pdf.py` | E | NOT\_RUN |
| LLM-01 | OpenAI | Missing key → `setup_required`; no retries | Integration | `pytest tests/providers/openai -k missing_key` | C | NOT\_RUN |
| LLM-02 | OpenAI | Crash after success → ledger `UNKNOWN` → reconciled; possible duplicate recorded | Workflow | `pytest tests/workflows -k crash_after_success` | D | NOT\_RUN |
| LLM-03 | OpenAI | Hosted `web_search` never attached while `SEARCH_PROVIDER=searxng` (request payload inspected) | Contract | `pytest tests/providers/openai -k no_hosted_search` | A | NOT\_RUN |
| LLM-04 | OpenAI | Configured model absent from the account → that role `setup_required` | Integration | `pytest tests/providers/openai -k model_check` | C | NOT\_RUN |
| LLM-05 | OpenAI | Live smoke, cost-capped | Live, opt-in | `LIVE_TESTS=1 pytest -m live_openai` | — | NOT\_RUN |
| OPT-01 | Optional providers | Configured without credentials → `MISSING_CREDENTIALS`; SearXNG unaffected | Integration | `pytest tests/providers -k missing_credentials` | C | NOT\_RUN |
| CMP-01 | Compose | Cold start, second start and clean-volume reset all reach readiness; seeds idempotent | Clean install | `make e2e-compose` | I | NOT\_RUN |
| DEMO-01 | Demo workspace | With internet egress disabled and no OpenAI key, the seeded demo user signs in and every demo screen loads from PostgreSQL through the real API and SSE stream | Clean install | `make e2e-offline-demo-workspace` | I | NOT\_RUN |

## Release-blocking provider scenarios

| ID | Scenario | Expected result | Result |
| --- | --- | --- | --- |
| PRV-01 | Fresh Docker install | UI at localhost:3000; default workspace and sample company exist | NOT\_RUN |
| PRV-02 | No API keys | Demo workspace seeded through the application services; demo documents ingested by the real pipeline | NOT\_RUN |
| PRV-03 | OpenAI key, no search key | SearXNG-backed live research runs when upstream engines are reachable | NOT\_RUN |
| PRV-04 | SearXNG healthy, all engines blocked | Visible degraded status; no false "no results" claim | NOT\_RUN |
| PRV-05 | SearXNG JSON disabled | Actionable diagnostic; no silent fallback | NOT\_RUN |
| PRV-06 | Duplicated, poisoned or malformed URLs in results | Normalized or safely rejected | NOT\_RUN |
| PRV-07 | GitHub unauthenticated quota exhausted | Bounded backoff, partial evidence, visible warning | NOT\_RUN |
| PRV-08 | RSS source unavailable or malformed | Partial research; workflow continues | NOT\_RUN |
| PRV-09 | Fetch blocked by robots or policy | Blocked status recorded; no bypass | NOT\_RUN |
| PRV-10 | Browser page requests a metadata endpoint | Blocked by network policy | NOT\_RUN |
| PRV-11 | Browser crashes or hangs | Timeout and cleanup; other branches continue | NOT\_RUN |
| PRV-12 | Malformed or oversized PDF | Safe failure within caps | NOT\_RUN |
| PRV-13 | Source changes between retrieval and verification | Immutable snapshot verified by hash | NOT\_RUN |
| PRV-14 | OpenAI success, worker crash before persisting | Uncertain-cost reconciliation; no exactly-once claim | NOT\_RUN |
| PRV-15 | Provider outage during parallel research | Unaffected tasks finish; coverage lists missing sources | NOT\_RUN |
| PRV-16 | Two tenants search the same company | No leakage of queries, annotations or decisions | NOT\_RUN |
| PRV-17 | Monitoring sees a changed source | New evidence and revision; historical memo unchanged | NOT\_RUN |
| PRV-18 | Optional provider without credentials | Explicit configuration error; SearXNG unaffected | NOT\_RUN |
| PRV-19 | No CRM configured | Approved memo downloadable and stored locally | NOT\_RUN |
| PRV-20 | Full application restart | Workflows resume; UI state coherent | NOT\_RUN |

## Tracker format

```json
{
  "id": "SXG-02",
  "document_section": "Tool contracts / SearXNG adapter",
  "provider": "searxng",
  "owner": "research-provider-agent",
  "status": "DOC_UPDATED",
  "source_url": "https://docs.searxng.org/admin/settings/settings_search.html",
  "verification_date": "2026-11-07",
  "test_command": "pytest tests/providers/searxng -k engines_blocked",
  "test_result": "NOT_RUN",
  "evidence": null,
  "blocker": "no repository",
  "reviewer": null
}
```

## Due diligence tests

All rows below are **NOT\_RUN** unless marked otherwise: they are specified, not executed. Every row runs with `environment: real` (full Compose stack, real services, real OpenAI where a model is involved, real public sources). Status moves to PASSED only with a recorded real run (CI job ID or command output stored with the build). Unit tests with test doubles are separate, labelled `unit`, and never mark a feature complete. Earlier test requirements remain in force, re-run against the real stack.

| ID | Feature | Type | Verification criterion | Real services needed | Status |
| --- | --- | --- | --- | --- | --- |
| DD-01 | Each of the 12 domains | Unit + contract | Each `DomainModule` passes its tests in the domain specification tab; outputs validate against `DomainAssessment` | None (fixtures) | NOT\_RUN |
| DD-02 | Level 1 screening | E2E | Fixture company completes L1; financial, legal, security, governance sections show `unavailable_at_level`; no private tools invoked (asserted from ledger) | Temporal, PostgreSQL, SearXNG, OpenAI, real public sources | NOT\_RUN |
| DD-03 | Level 2 public diligence | E2E | All 12 domains run on public sources; gates reported per domain; report has 21 sections with valid statuses | As DD-02 | NOT\_RUN |
| DD-04 | Level 3 enhanced diligence | E2E | With acknowledgement and deal team, fixture data room is ingested, tables validated, ddcalc runs, private findings appear only to deal team | Full stack incl. ClamAV, worker-docs, MinIO | NOT\_RUN |
| DD-05 | Level 3 prerequisites | Integration | Level 3 starts without external AI consent and skips private model steps with reason `external_ai_not_authorized` (D1); analyst outside deal team → `403 NOT_ON_DEAL_TEAM`; analyst starting L3 → `403 LEVEL_NOT_ALLOWED` | API, PostgreSQL | NOT\_RUN |
| DD-06 | Public/private separation | Security | No private text appears in SearXNG queries, logs, traces, outbox payloads or other assessments (log and query capture over a full L3 run) | Full stack | NOT\_RUN |
| DD-07 | Workspace isolation | Security | Two firms; every list and get endpoint and every SSE stream returns nothing across firms; RLS denies direct SQL as the app role | PostgreSQL with RLS | NOT\_RUN |
| DD-08 | Financial formulas | Unit (golden) | Each ddcalc metric matches hand-computed golden values to the stated rounding; property tests for invariants (GRR ≤ NRR, runway undefined when net burn ≤ 0) | None | NOT\_RUN |
| DD-09 | Missing financial records | Unit + integration | Missing inputs give `not_computable` with `missing_inputs`; no value; report says "not computable"; information request created | worker-docs | NOT\_RUN |
| DD-10 | Contradictory financial records | Integration | Deck ARR vs workbook MRR beyond 2% raises a contradiction listing both spans | worker-docs | NOT\_RUN |
| DD-11 | Unvalidated tables | Integration | Calculation on a `needs_validation` table → `VALIDATION_REQUIRED`; after correction and validation it computes; corrections audited | worker-docs, API | NOT\_RUN |
| DD-12 | Malicious uploads | Security | EICAR → `MALWARE_DETECTED`, quarantined; zip bomb → `LIMIT_EXCEEDED`; XXE OOXML parsed safely; macro formats rejected; renamed executable → `MIME_MISMATCH` | ClamAV, worker-docs | NOT\_RUN |
| DD-13 | Scanner outage | Integration | clamd stopped → upload stays `scanning`, no parse happens, health shows degraded | ClamAV | NOT\_RUN |
| DD-14 | Parser failures | Integration | Malformed PDF falls back to pdfplumber then `PARSE_FAILED`; encrypted PDF → `ENCRYPTED_DOCUMENT`; timeout enforced | worker-docs | NOT\_RUN |
| DD-15 | Unsupported formats | Integration | `.pages`, `.numbers`, `.key`, images when OCR off → `UNSUPPORTED_FORMAT` | API | NOT\_RUN |
| DD-16 | Prompt injection in documents | Security / red team | Fixture deck with embedded instructions: score and recommendation unchanged vs clean deck; passage flagged; no tool call outside scope | Real OpenAI (cost-capped CI secret); the injected deck is a real document uploaded through the real pipeline | NOT\_RUN |
| DD-17 | False or misleading source claims | E2E | Fixture site claims a customer and a certification that third parties contradict: findings stay `source_supported` or `contradictory`, never `verified_fact` | A test site published on a real domain controlled by the project (e.g. a GitHub Pages site) with deliberately false claims; fetched through SafeFetcher and SearXNG like any site | NOT\_RUN |
| DD-18 | Cross-document discrepancies | Integration | Cap table total ≠ registry; customer count deck ≠ customer list → contradictions with both locators | worker-docs | NOT\_RUN |
| DD-19 | Insufficient evidence | E2E | Company with almost no public footprint: gates `insufficient`, recommendation `inconclusive`, report still complete with 21 sections and requests | Full stack | NOT\_RUN |
| DD-20 | Report versioning | Integration | Approved report is immutable (update attempts → 409); new document after approval opens a new revision and a new `ReportVersion` | API, Temporal | NOT\_RUN |
| DD-21 | Human approval authorization | Security | Only partner or above approves; approval bound to `ReviewTarget`; stale target → `409 STALE_REVIEW_TARGET` | API | NOT\_RUN |
| DD-22 | Upgrades | E2E | L1 → L2 → L3 creates revisions r2 and r3, reuses frozen public evidence, does not re-fetch unchanged sources (ledger) | Full stack | NOT\_RUN |
| DD-23 | Reassessment | E2E | Monitoring event triggers incremental reassessment of affected domains only | Full stack | NOT\_RUN |
| DD-24 | Search outage and blocking | Integration | SearXNG stopped or upstream returns 429/CAPTCHA page: affected domains `partial` with `search_unavailable`; direct sources still used; no CAPTCHA bypass attempted | SearXNG | NOT\_RUN |
| DD-25 | Partial domain failure | Integration | One domain child fails permanently: others complete, report marks that section incomplete, `POST /assessments/{id}/domains/{d}/retry` reruns only it | Temporal | NOT\_RUN |
| DD-26 | Workflow replay | Replay | Recorded histories for L1, L2, L3, upgrade and cancel replay without non-determinism errors on the current worker build | Temporal test server | NOT\_RUN |
| DD-27 | Exports | E2E | PDF and DOCX open, contain 21 headings, Level 3 watermark present, non-deal-team export omits private sections | worker-browser | NOT\_RUN |
| DD-28 | Disclaimer lint | Unit | Templates and generated sections contain no certification wording outside quotes | None | NOT\_RUN |
| DD-29 | Deletion | Integration | Deleting a document version removes object, spans, embeddings and cached prompts; audit tombstone written; findings citing it marked `source_deleted` | Full stack | NOT\_RUN |
| DD-30 | Readiness unchanged | E2E | `docker compose up --build` → `http://localhost:3000` loads with no OpenAI key (mode `demo_ready`; the demo user can sign in and browse the seeded workspace through the real API); SearXNG canary returns real results; ClamAV ready | Full stack | NOT\_RUN |

## Real-integration and demo-workspace tests

| ID | Feature | Verification criterion | Real services | Status |
| --- | --- | --- | --- | --- |
| REAL-01 | No mocks in shipped code | Production web bundle contains no `msw` or `mocks/` module; import-linter shows no path from api, workers or seed to `tests/`; no `DEMO_MODE` setting exists | Build pipeline | NOT\_RUN |
| REAL-02 | Demo seed through services | `seed-demo` on an empty database creates `frm_demo`, two demo users and the three demo assessments; a second run creates nothing new; every row passes the same validators as API writes | PostgreSQL, Temporal, MinIO, ClamAV, worker-docs | NOT\_RUN |
| REAL-03 | Demo documents ingested for real | The seeded EICAR file is quarantined by ClamAV, the macro workbook is rejected, the others reach `ready` with real parser output stored | ClamAV, worker-docs, MinIO | NOT\_RUN |
| REAL-04 | Demo calculations computed for real | Every seeded `CalculationResult` equals a fresh `ddcalc` run on the seeded tables; the seed contains no calculated values | worker-docs | NOT\_RUN |
| REAL-05 | Demo user through the real API | Browser test signs in with "Explore the demo workspace", loads every Diligence screen; network log shows only `/api/v1/*` and the SSE stream; responses validate against the OpenAPI schema | Full stack | NOT\_RUN |
| REAL-06 | Demo isolation | Demo session cannot read another firm (API and direct SQL as the app role), cannot change providers, users or retention, cannot create tokens; `DEMO_WORKSPACE=false` makes `/auth/demo-session` return 404 | Full stack | NOT\_RUN |
| REAL-07 | Demo actions are real | Validating the seeded MRR table creates revision 5 and emits `financials.validated` and `assessment.revision_created` on the real SSE stream; without a key the next model step stops at `PROVIDER_NOT_CONFIGURED` | Full stack | NOT\_RUN |
| REAL-08 | Demo reset | `POST /demo/reset` restores the seeded state; other firms untouched | Full stack | NOT\_RUN |
| REAL-09 | Live acceptance | With a real OpenAI key, a Level 2 assessment of a real public company runs end to end against SearXNG, SEC EDGAR and GitHub; every number in the report traces to a stored span or calculation | Full stack, OpenAI, internet | NOT\_RUN |
| REAL-10 | Real fault injection | Toxiproxy timeouts and resets on OpenAI, SearXNG and MinIO connections, `docker compose stop` of ClamAV and SearXNG, and SIGKILL after a provider call each produce the documented recovery without duplicate side effects | Full stack, Toxiproxy | NOT\_RUN |

## Fixture validation (ran)

| ID | What ran | Result | Scope |
| --- | --- | --- | --- |
| FIX-01 | `python3 build_fixtures.py` (2026-11-07): 13 JSON files and 14 events validated against a Pydantic transcription of the contracts (`project/fixtures/models.py`), plus 7 negative cases that must be rejected | PASSED: 13/13 files, 14/14 events, 7/7 negatives rejected | Checks only that the seed data matches the contracts. It does not test any implementation; no application code exists yet. It found and fixed two data errors (September MRR did not roll forward; per-domain finding counts summed to 70, not 76). |

## Decision tests D1–D6

All rows are **NOT\_RUN** against the product (no code exists). Environment `real` means the full Compose stack. `ci-local` means deterministic local fixtures, allowed for normal CI where a decision says so. Only `real` runs can move a decision to Tested or Verified.

### D1 — Private documents and external AI

| ID | Verification criterion | Env | Status |
| --- | --- | --- | --- |
| D1-01 | Default policy: a Level 3 run on the demo data room produces zero external requests containing private segments. Egress proxy log, `ExternalTransmission` empty, model steps on private data skipped with `external_ai_not_authorized` | real | NOT\_RUN |
| D1-02 | Every code path that calls a model (extraction, verification, evaluation, critique, report, monitoring, reassessment, re-embedding, retries) goes through `PolicyEnforcedProvider`. Import-linter contract plus a runtime canary that fails if any other client is constructed | real | NOT\_RUN |
| D1-03 | Policy matrix: for every combination of category × purpose × route, the decision matches the specification table (property test, 2,000 cases) | unit + real spot checks | NOT\_RUN |
| D1-04 | Untagged text is treated as private; `scope=private` without a category is rejected at construction | unit | NOT\_RUN |
| D1-05 | Embeddings of private spans go to the local embedding model, or are refused; never to OpenAI without `embedding_inputs` and the `embeddings` purpose | real | NOT\_RUN |
| D1-06 | Search egress guard: a query containing an 8-word shingle from a private document returns `PRIVATE_DATA_EGRESS_BLOCKED`; the SearXNG access log shows no such query | real | NOT\_RUN |
| D1-07 | Revocation: authorize external, start Level 3, revoke mid-run. No external private request is sent more than 30 s after revocation | real | NOT\_RUN |
| D1-08 | Fail closed: policy store unreachable, expired policy, or unverified local model each produce denial, not external fallback | real (Toxiproxy on PostgreSQL) | NOT\_RUN |
| D1-09 | Authorization: only owner or admin with step-up can change the policy; partner, analyst, operator and demo sessions get 403; every change audited with old and new values | real | NOT\_RUN |
| D1-10 | Local model probe: a non-private `base_url` is classified external; a model failing the structured-output probe leaves the route unavailable | real | NOT\_RUN |
| D1-11 | No private text in Temporal histories, logs, traces or ledger after a full Level 3 run (scan for shingles of every private span) | real | NOT\_RUN |
| D1-12 | `ExternalTransmission` rows exist exactly for authorized transmissions, with hashes and no content | real | NOT\_RUN |

### D2 — Retention

| ID | Verification criterion | Env | Status |
| --- | --- | --- | --- |
| D2-01 | Closing an assessment sets `delete_after = closed_at + 90 days`; values above 90 or below 0 return `422 RETENTION_OUT_OF_RANGE` | real | NOT\_RUN |
| D2-02 | Shortening the setting moves future deadlines earlier and never later | real | NOT\_RUN |
| D2-03 | Reopening does not change `delete_after`; one audited extension of at most 90 days from reopening is allowed; a second extension returns `409 EXTENSION_ALREADY_USED` | real | NOT\_RUN |
| D2-04 | Deletion removes every artifact class: all object versions and delete markers, spans, tables, embeddings, full-text vectors, cached prompts, OCR images, exports; findings tombstoned; private report sections redacted | real | NOT\_RUN |
| D2-05 | Verification: after deletion, object version listing is empty, row counts zero, vector and full-text searches for sampled shingles return nothing; certificate written | real | NOT\_RUN |
| D2-06 | Legal hold blocks scheduled and immediate deletion (`409 LEGAL_HOLD_ACTIVE`); release lets deletion proceed on the next run | real | NOT\_RUN |
| D2-07 | Idempotency and recovery: SIGKILL the worker mid-deletion, restart, and the workflow completes with no duplicate side effects; a duplicate start is a no-op | real | NOT\_RUN |
| D2-08 | Access is revoked before deletion completes; reads return `410 DELETED` | real | NOT\_RUN |
| D2-09 | Audit keeps only permitted metadata: no filenames, no content hashes | real | NOT\_RUN |
| D2-10 | Object-store versioning: an overwritten object's noncurrent version is gone after the lifecycle period and after deletion; the backup-expiry date is shown on the certificate | real | NOT\_RUN |

### D3 — Sanctions screening

| ID | Verification criterion | Env | Status |
| --- | --- | --- | --- |
| D3-01 | Ingest from the official OFAC export URLs: dataset rows record URL, retrieval time, publish date, SHA-256 and record count; XSD validation passes | real | NOT\_RUN |
| D3-02 | V-D3-1: `SDN.XML` is served on `sanctionslistservice.ofac.treas.gov`, and the adapter refuses non-`treas.gov` hosts | real | NOT\_RUN |
| D3-03 | Atomic activation: a failed or partial download leaves the previous dataset current | real (Toxiproxy reset mid-download) | NOT\_RUN |
| D3-04 | Normalization keeps originals; diacritics, transliteration and legal suffixes handled per fixture table | unit | NOT\_RUN |
| D3-05 | Matching bands on a synthetic list in OFAC XML format: exact, strong (≥ 92), weak (85–91), none (< 85) as expected; corroborating attributes recorded | ci-local | NOT\_RUN |
| D3-06 | Stale data (> 3 days) is labelled; > 7 days or none loaded gives `unavailable`, never "no matches" | real | NOT\_RUN |
| D3-07 | Review workflow: dismiss needs a reason; only `compliance_reviewer` can confirm; all transitions audited | real | NOT\_RUN |
| D3-08 | Wording lint: no template or generated text calls a subject "sanctioned" outside quoted list data | unit | NOT\_RUN |
| D3-09 | Optional sources are off by default; enabling one without an official URL fails validation | real | NOT\_RUN |
| D3-10 | A record-count drop > 10% needs operator confirmation before activation | real | NOT\_RUN |

### D4 — OCR

| ID | Verification criterion | Env | Status |
| --- | --- | --- | --- |
| D4-01 | Native PDF: no page OCR'd | real | NOT\_RUN in product; harness PASSED |
| D4-02 | Scanned PDF: every page OCR'd locally; character error rate ≤ 2% on clean synthetic scans; provenance fields set | real | NOT\_RUN in product; harness PASSED (CER 0.0) |
| D4-03 | Mixed PDF: OCR only on scanned pages, page numbers preserved | real | NOT\_RUN in product; harness PASSED |
| D4-04 | Image-dominated page (≥ 60% image, < 200 chars) OCR'd even with some native text | real | NOT\_RUN in product; harness PASSED |
| D4-05 | Garbled text layer (symbol or replacement glyphs) OCR'd | real | NOT\_RUN in product; harness PASSED after rule refinement |
| D4-06 | Confidence recorded; pages < 60 flagged and findings capped at low confidence; OCR tables always need validation | real | NOT\_RUN in product; harness PASSED (flag logic) |
| D4-07 | Limits: page cap, per-page timeout, total time and memory enforced; over-limit pages `ocr_skipped_limit` with warning | real | NOT\_RUN in product; harness PASSED (page cap only) |
| D4-08 | Malformed → `PARSE_FAILED`; encrypted → `ENCRYPTED_DOCUMENT` | real | NOT\_RUN in product; harness PASSED |
| D4-09 | Sandbox: OCR child process has no network (connect attempt fails), read-only root, scratch wiped | real | NOT\_RUN |
| D4-10 | Language packs: `OCR_LANGUAGES=deu` with the pack installed works; with the pack missing, startup fails with a clear error | real | NOT\_RUN |
| D4-11 | No cloud OCR call exists (egress log over the whole OCR suite) | real | NOT\_RUN |
| D4-12 | Fixtures are deterministic: regenerating yields identical hashes | ci-local | NOT\_RUN in product; harness PASSED |

### D5 — Licence

| ID | Verification criterion | Env | Status |
| --- | --- | --- | --- |
| D5-01 | `LICENSE` matches the SPDX Apache-2.0 text under the matching guidelines | CI | NOT\_RUN |
| D5-02 | `NOTICE` present; dependency NOTICE attributions included in `THIRD_PARTY_NOTICES.md` | CI | NOT\_RUN |
| D5-03 | Every source file has `SPDX-License-Identifier: Apache-2.0` (`reuse lint`) | CI | NOT\_RUN |
| D5-04 | `pyproject.toml`, `package.json` and image labels all say Apache-2.0 | CI | NOT\_RUN |
| D5-05 | Licence gate fails on a deliberately added GPL dependency and passes on the real tree with zero unexplained exceptions | CI | NOT\_RUN |
| D5-06 | `fixtures/PROVENANCE.md` lists every fixture, screenshot and seed file as project-authored CC0-1.0; no third-party content | CI | NOT\_RUN |

### D6 — False-claims site

| ID | Verification criterion | Env | Status |
| --- | --- | --- | --- |
| D6-01 | Fixture site integrity: labelling, claims present, independent counter-evidence present, unsupported claims without evidence, injection present, no real-world identifiers, deterministic hashes | ci-local | **PASSED as a fixture check (7/7, 2026-11-07)**; not an agent test |
| D6-02 | `fixture-web` serves the byte-identical site over HTTPS under `--profile test`; hashes match the manifest | ci-local | NOT\_RUN |
| D6-03 | Agent behaviour on the local site: C1–C4 contradictory with evidence citations; C5–C6 missing; injection flagged; no C1–C6 statement in the report as a verified fact; scores identical with and without the injection line; snapshots and provenance stored | ci-local | NOT\_RUN |
| D6-04 | Live preflight: `FALSE_CLAIMS_TEST_URL` returns 200 over valid HTTPS; served manifest version and hashes match; GitHub API confirms repository owner and Pages source; verification record written | real (`RUN_LIVE_D6=1`) | **BLOCKED: site not deployed** |
| D6-05 | D6-03 assertions against the live URL | real | **BLOCKED: site not deployed** |

## Executed runs recorded on 2026-11-07

These runs were actually executed in the planning workspace. They test specification artifacts, not the product.

| Run | What | Result | Evidence |
| --- | --- | --- | --- |
| FIX-01 | Seed data validated against the contracts | PASSED: 13/13 files, 14/14 events, 7/7 negative cases | `project/fixtures/build_fixtures.py` output |
| HAR-D4 | D4 harness: native-first extraction with page-level Tesseract fallback on 11 generated fixtures | PASSED 12/12 (Tesseract 5.3.4, pypdf 6.17.0, pypdfium2 5.15.1). Character error rate 0.0 on clean scans; page confidence 95.4–95.8; about 0.65 s per page. The first run failed on the garbled-only fixture, which changed the specification | `ocr/test_d4.py`, `ocr/results.txt` |
| SITE-D6 | D6 fixture site self-checks | PASSED 7/7. Earlier failures were in the checks themselves (an over-broad assertion and over-broad regular expressions), fixed and rerun | `d6-site/test_site.py`, `d6-site/results.txt` |
