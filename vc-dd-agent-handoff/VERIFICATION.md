# Verification guide: is the implementation correct?

Use this after the coding agent says it is finished. It tells a reviewer (person or agent) what to run, what must be true, and what evidence to keep. It is written against the specification in `docs/`; where a test ID is named, the full criterion is in `docs/testing-and-acceptance.md`.

**Status of this guide:** written 2026-11-07, before any implementation existed. Only the commands in Part 1 have been executed (they passed). Every command in Parts 2–11 is proposed. Service names, ports and the `/api/v1` prefix follow the master plan. If the implementation names things differently, adapt the command, keep the criterion unchanged, and note the adaptation in the report.

## How to use it

1. Work on a **clean checkout** of the implementation at a fixed commit, on a machine with Docker, at least 4 CPU and 8 GB RAM, internet access, and a cost-capped OpenAI key kept out of the repo.
2. Go through the parts in order. Parts 1–4 need no OpenAI key and must pass before anything else is worth checking.
3. For every test ID, write one evidence record (`verify/evidence_record.template.json`): environment, commit SHA, exact command, result, artifact link.
4. Fill in the sign-off tables at the end. A row without an artifact is **not passed**, whatever the agent's report says.

## Evidence rules

- **Only `environment: real` results can mark a feature Tested or Verified.** `ci-local` counts only where a decision says so (D3-05, D4-12, D6-01..D6-03). `unit` results never count.
- A test that only asserts a mock was called does not count.
- A skipped test is not a pass. D6-04 and D6-05 must show **BLOCKED: site not deployed** until the Pages site exists; a "pass" there without a live URL and a verification record is a red flag.
- Screenshots and logs must come from the run being reported. Check timestamps and commit SHA.
- Gate H: someone other than the implementer reruns the release-blocking commands and gets the same result.

## Automatic fail conditions

Any one of these fails the implementation, regardless of other results:

| # | Condition | How to detect |
| --- | --- | --- |
| F1 | UI does not load at `http://localhost:3000` without an OpenAI key | Part 3 |
| F2 | SearXNG is only health-checked, or needs a paid or third-party account | Part 3, SXG-10, SXG-11 |
| F3 | Mock layer, `DEMO_MODE`, fake provider or test-hook routes in shipped code | Part 2, REAL-01 |
| F4 | Demo screens served from anything other than PostgreSQL through the real API and SSE | REAL-05 network log |
| F5 | A number in a report that does not trace to a stored span, validated table cell or `ddcalc` result | REAL-09, DD-08, DD-09 |
| F6 | Private document text in a search query, log, trace, Temporal history, ledger or external request without D1 authorization | D1-01, D1-06, D1-11, DD-06 |
| F7 | Output that states legal compliance, certification, or that a subject "is sanctioned" | DD-28, D3-08, Part 2 lint |
| F8 | A live key in the repo, an image layer, the browser bundle, logs or fixtures | Part 2, image scan below |
| F9 | Project licence not Apache-2.0, or licence gate disabled or full of unexplained exceptions | D5-01..D5-05 |
| F10 | Any reported pass without an artifact, or D6 reported as verified without the deployed site | Evidence review |
| F11 | CAPTCHA evasion, proxy rotation, stealth scraping, or login automation on social networks | Code review of fetch/browser adapters, DD-24 |

---

## Part 1. Package integrity and spec harnesses (executed 2026-11-07)

These prove the hand-off material is intact. They say nothing about the product.

```bash
cd vc-dd-agent-handoff
sha256sum -c --quiet MANIFEST.sha256 && echo MANIFEST OK
pip install pydantic pytest selectolax pypdf pdfplumber pypdfium2 pytesseract rapidfuzz reportlab pillow
bash verify/run_spec_harnesses.sh
```

| Check | Pass criterion | Last recorded result |
| --- | --- | --- |
| Manifest | `MANIFEST OK` | OK at packaging |
| FIX-01 | 13/13 files, 14/14 events, 7/7 negatives rejected | Passed |
| HAR-D4 | 12 passed (needs Tesseract 5.x on PATH) | 12 passed, Tesseract 5.3.4 |
| SITE-D6 | 7 passed | 7 passed |

The implementation must also keep these passing: the D4 fixtures and thresholds and the D6 site must be carried into the repo unchanged (the D6 site byte-identical, version `d6-false-claims@1.0.0`).

## Part 2. Static checks on the repository

```bash
# build the production web bundle first, so the bundle scan has something to scan
docker compose build web
docker compose run --rm --no-deps web sh -c 'ls .next >/dev/null'   # adapt to the real build output path
bash verify/repo_static_checks.sh /path/to/repo /path/to/repo/apps/web/.next
```

Pass: script exits 0. `SKIP` lines must be resolved (install `reuse`, point at the real bundle). Then:

```bash
# no secrets baked into images
for img in $(docker compose config --images); do
  docker save "$img" | tar -xO 2>/dev/null | grep -a -m1 -E 'sk-(proj-)?[A-Za-z0-9_-]{20,}' && echo "KEY FOUND IN $img"
done
# no host port for SearXNG, Postgres, Temporal gRPC, egress proxy
docker compose config | grep -A12 -E '^\s+(searxng|postgres|temporal|egress-proxy):' | grep -E '^\s+ports:' && echo "UNEXPECTED PORT"
```

Pass: no `KEY FOUND`, no `UNEXPECTED PORT`. Also confirm by reading: only `PolicyEnforcedProvider` constructs a model client (D1-02), and the import-linter contract that forbids production code importing `tests/` exists and runs in CI.

## Part 3. Clean install, no OpenAI key (E2E-01, E2E-02, E2E-24, DD-30, CMP-01, PRV-01, SXG-10)

```bash
cp .env.example .env            # leave OPENAI_API_KEY empty
grep -E '^OPENAI_API_KEY=$' .env
docker compose down -v
time docker compose up --build -d
docker compose ps                # every long-running service healthy; one-shots exited 0
```

| # | Command | Pass criterion |
| --- | --- | --- |
| 3.1 | `curl -s -o /dev/null -w '%{http_code}\n' http://localhost:3000` | `200`, within the time the README promises (ClamAV may take minutes) |
| 3.2 | `curl -fsS http://localhost:8000/health/ready \| jq` | All dependency checks pass |
| 3.3 | `curl -fsS http://localhost:8000/api/v1/system/status \| jq '{mode, demo_workspace, search}'` | `mode` is `demo_ready` (or `setup_required` if `DEMO_WORKSPACE=false`); `demo_workspace: "ready"`; `search.state: "ok"`, `json_enabled: true`, `last_canary_at` set |
| 3.4 | SearXNG function, from inside the network: `docker compose exec api python -c "import httpx;r=httpx.get('http://searxng:8080/search',params={'q':'open source software','format':'json'},timeout=20).json()['results'];print(len(r),all(x['url'].startswith('http') for x in r))"` | At least `3 True`. Health alone is not enough |
| 3.5 | `docker compose port searxng 8080` | No host mapping |
| 3.6 | Open `http://localhost:3000` in a browser | Setup banner explains the missing key; no request for a search key; "Explore the demo workspace" offered |
| 3.7 | `docker compose restart && docker compose ps` then count seeded rows before and after (e.g. `SELECT count(*) FROM assessments WHERE firm_id='frm_demo'`) | Same counts; no duplicate seeds or migrations (E2E-24) |
| 3.8 | `docker compose down -v && docker compose up -d` | Comes back to the same state from empty volumes |
| 3.9 | Stop upstream access for SearXNG only (e.g. block its egress) and wait for the canary | `search.state: "degraded"`, readiness still passes (SXG-10); UI shows degraded, not "no results" |

## Part 4. Demo workspace through the real API (REAL-01 to REAL-08, DEMO-01)

```bash
J=/tmp/demo.jar; API=http://localhost:8000/api/v1
curl -fsS -c $J -X POST $API/auth/demo-session -o /dev/null -w '%{http_code}\n'
curl -fsS -b $J "$API/assessments?view=summary" | jq 'length, [.[].level]'
curl -fsS -b $J $API/me | jq '{firm_id, role}'
timeout 8 curl -sN -b $J "$API/events/stream?audience=research" | head -20
```

| ID | Check | Pass criterion |
| --- | --- | --- |
| REAL-02 | Seed through services | `frm_demo`, `demo@thesis.local` (partner, on the L3 deal team), `demo-analyst@thesis.local` (not on it), three demo assessments. Running `docker compose run --rm seed-demo` again creates nothing new. Seed code calls application services, not raw SQL inserts (read the code) |
| REAL-03 | Real ingestion | Seeded EICAR file is `quarantined` with `MALWARE_DETECTED`; macro workbook rejected; other demo documents `ready` with parser output stored; objects exist in the object store encrypted |
| REAL-04 | Real calculations | Every seeded `CalculationResult` equals a fresh `ddcalc` run on the seeded validated tables; the seed files contain no calculated values |
| REAL-05 | Real API in the browser | Playwright signs in with "Explore the demo workspace" and opens every Diligence screen (overview, domains, findings, report, data room, financial validation, risks, contradictions, requests, settings). Network log shows only `/api/v1/*` and the SSE stream. Responses validate against the OpenAPI schema |
| REAL-06 | Isolation | Demo session gets 403/404 for another firm's IDs (API and direct SQL as the app role under RLS); cannot change providers, users or retention; cannot create tokens. With `DEMO_WORKSPACE=false`, `POST /auth/demo-session` returns 404 |
| REAL-07 | Actions are real | Validating the seeded MRR table creates a new revision and emits `financials.validated` and `assessment.revision_created` on the live SSE stream; the next model step stops with `PROVIDER_NOT_CONFIGURED` |
| REAL-08 | Reset | `POST /demo/reset` restores the seed; other firms untouched |
| DEMO-01 | Offline demo | With internet egress disabled and no key, sign-in and every demo screen still load from PostgreSQL |
| — | Restricted view | Signed in as `demo-analyst@thesis.local`, deal-team-only findings and report sections are absent (not redacted placeholders that leak counts beyond what the spec allows) |

## Part 5. Live acceptance with a real key (REAL-09, E2E-03, PRV-03, LLM-04, LLM-05)

```bash
export OPENAI_API_KEY=<cost-capped key>   # in .env or the secret store, never committed
docker compose up -d && curl -fsS $API/system/status | jq .mode   # live_ready
```

| ID | Check | Pass criterion |
| --- | --- | --- |
| LLM-04 | Model availability check at startup | Configured model IDs verified against the account; a missing model puts that role in `setup_required`, not a retry loop |
| REAL-09 | Level 2 on a real public company | Runs end to end against SearXNG, SEC EDGAR and GitHub. Every number in the report resolves to a stored span or calculation (spot-check at least 20 numbers through the citation viewer and `GET /evidence/{id}/citation`) |
| E2E-03 | Usage and key handling | Usage and cost shown; key never appears in UI, logs, events or exports |
| — | Report shape | Exactly 21 sections, each with status `supported`, `incomplete`, `not_applicable` or `unavailable_at_level`; JSON export validates against `/schemas/ddreport@1.json`; disclaimers on sections 10, 12, 13 |
| — | Four measures | Source reliability, claim confidence, evidence coverage and attractiveness are shown separately; nothing combines them into one number |
| — | Recommendation | One of `advance`, `hold`, `pass`, `inconclusive` (+ `conditions[]` only with `advance`) |

## Part 6. Due diligence features (DD-01 to DD-30)

Run each ID from `docs/testing-and-acceptance.md` in `environment: real` unless the row says otherwise. Highest-risk checks to look at yourself:

| Area | IDs | What to look for |
| --- | --- | --- |
| Levels | DD-02, DD-03, DD-04, DD-05, DD-22 | L1 shows financial/legal/security/governance as `unavailable_at_level` and calls no private tool (check the ledger). L3 starts without external-AI consent and skips private model steps with `external_ai_not_authorized`. Upgrades reuse frozen public evidence |
| Numbers | DD-08, DD-09, DD-10, DD-11 | Golden values match; missing inputs give `not_computable` with `missing_inputs` and **no value**; unvalidated tables refuse with `VALIDATION_REQUIRED`; ARR vs MRR beyond 2% raises a contradiction |
| Files | DD-12 to DD-15 | EICAR quarantined, zip bomb `LIMIT_EXCEEDED`, XXE safe, macros rejected, renamed executable `MIME_MISMATCH`, ClamAV down keeps upload in `scanning` |
| Honesty | DD-16, DD-17, DD-19, DD-28 | Injected deck does not change score or recommendation; false claims never become `verified_fact`; thin-footprint company gets `inconclusive` with a complete 21-section report; no certification wording |
| Isolation | DD-06, DD-07 | Capture logs and SearXNG queries over a full L3 run: no private text anywhere outside the data room |
| Durability | DD-20, DD-21, DD-25, DD-26 | Approved report immutable (409); stale review target 409; single domain retry; replay of recorded histories without non-determinism errors |
| Exports | DD-27 | PDF and DOCX open with 21 headings; L3 watermark; non-deal-team export omits private sections |

## Part 7. Decisions D1–D6

| Decision | IDs | Key pass criteria | May end as |
| --- | --- | --- | --- |
| D1 External AI | D1-01 … D1-12 | Default policy: zero external requests containing private segments (egress log, empty `ExternalTransmission`). Search egress guard returns `PRIVATE_DATA_EGRESS_BLOCKED` and SearXNG log shows no such query. Revocation takes effect within 30 s. Fail closed when the policy store is down. Only owner/admin with step-up can change policy | Tested → Verified |
| D2 Retention | D2-01 … D2-10 | 0–90 days, shorten only, one extension, legal hold blocks deletion, deletion removes every artifact class and writes a `DeletionCertificate` with verification booleans all true; SIGKILL mid-deletion recovers without duplicates; `BACKUP_RETENTION_DAYS` ≤ 35 | Tested → Verified |
| D3 Sanctions | D3-01 … D3-10 | Official OFAC SDN + consolidated only by default, XSD-validated, hashed, atomic activation; bands exact / strong ≥ 92 / weak 85–91; stale > 7 days gives `unavailable`, never "no matches"; only `compliance_reviewer` confirms; nothing calls a subject "sanctioned". D3-02 resolves blocker B3 | Tested → Verified |
| D4 OCR | D4-01 … D4-12 | Product reproduces the harness results on the same fixtures (native untouched, scanned and mixed OCR'd per page, garbled layer and image-dominated pages OCR'd, confidence < 60 flagged, limits enforced, malformed/encrypted errors). Plus sandbox (no network from OCR child), language packs, no cloud OCR | Tested → Verified |
| D5 Licence | D5-01 … D5-06 | Apache-2.0 LICENSE, NOTICE, SPDX headers (`reuse lint`), manifests agree, licence gate fails on a seeded GPL dependency and passes the real tree, fixture provenance file. B5 licences checked at pin | Tested → Verified |
| D6 False-claims site | D6-01 … D6-05 | D6-01 to D6-03 in `ci-local`: `fixture-web` (profile `test` only) serves the byte-identical site; agent marks C1–C4 contradictory with citations, C5–C6 missing, flags the injection, scores identical with and without it. D6-04/05 need `RUN_LIVE_D6=1` and the deployed Pages URL | **Pending deployment and verification** until B2 is done. Never Verified without a live URL, matching manifest hashes and a verification record |

## Part 8. Providers and security (Gates C, E)

Run the provider rows (SXG-01..11, FET-01..06, BRW-01..04, GH-01..05, RSS-01..03, EDG-01, PDF-01, LLM-01..05, OPT-01) and the 20 release-blocking scenarios PRV-01..PRV-20. Minimum spot checks:

SSRF spot check: run the implementation's FET-01 suite, then additionally feed these URLs through the real `fetch_url` tool path (and through `render_page`) and confirm each returns `SOURCE_BLOCKED` with `blocked_reason: ssrf` and that the egress proxy log shows no connection to the target: `http://169.254.169.254/latest/meta-data/`, `http://127.0.0.1:8000/`, `http://[::1]/`, `http://0x7f000001/`, `http://2130706433/`, and a public hostname you control that redirects to `http://10.0.0.1/`.

| Check | Pass criterion |
| --- | --- |
| SXG-11 | Default config contains no paid search provider or key |
| LLM-03 | Hosted `web_search` is never attached while `SEARCH_PROVIDER=searxng` (inspect request payloads) |
| FET-01/02, BRW-01/04, E2E-13 | Private IPs, metadata endpoint, rebinding, redirects to private space, downloads, WebSockets all blocked |
| FET-04, DD-24 | robots/policy blocks recorded with reason; CAPTCHA or 429 pages produce `partial` with `search_unavailable`; no bypass code exists |
| SXG-08, E2E-06, E2E-14 | Tenant B never sees tenant A's cached queries, artifacts, vectors or workflows |
| GH-01/02, EDG-01 | Rate limits honoured; EDGAR User-Agent present; ≤ 5 req/s |

## Part 9. Fault injection and durability (REAL-10, E2E-04 … E2E-23)

| Fault | How | Pass criterion |
| --- | --- | --- |
| Timeouts and resets | Toxiproxy on OpenAI, SearXNG, PostgreSQL, object store, ClamAV | Documented recovery; no duplicate side effects |
| Service down | `docker compose stop clamav`, `stop searxng` | Uploads wait in `scanning`; search `degraded`; research continues on direct sources |
| Crash after success | SIGKILL a worker right after a provider call returns | Ledger records `UNKNOWN`, reconciles, shows possible duplicate spend (E2E-07, LLM-02) |
| Budget race | 20 tasks reserve the last budget | No overcommit; losers get `BUDGET_EXHAUSTED` (E2E-08) |
| Concurrent review | Two reviewers decide at once | One applies; other gets `409 REVIEW_ALREADY_DECIDED` (E2E-15) |
| Restart | Full `docker compose restart` mid-research and mid-review | Workflows resume; no decision lost (E2E-20, PRV-20) |

## Part 10. UI journeys (Gate F)

Playwright against the real web app and API with `frm_demo` seeded; no MSW, no event injection. Check against `docs/thesis-ui.md` and the prototype for layout, and against the API for data.

| Journey | Pass criterion |
| --- | --- |
| No key | Banner, demo entry, no search-key prompt, all demo screens load |
| Investor | Submit (with key) → live progress by stage and domain → report → decision; SSE reconnect with `Last-Event-ID` |
| Level picker | L3 disabled with the correct reason when prerequisites are missing; never asks for "provider terms acceptance" (errata E5) |
| Data room | Upload shows scanning → parsing → ready; quarantined and rejected states; OCR provenance (engine, language, confidence, low-confidence flag) on spans |
| Financial validation | Correct a cell with a reason, validate, see new revision and recomputed metrics |
| Sanctions review | Potential matches shown as potential; confirm button only for `compliance_reviewer` |
| Settings | External AI policy (off by default, owner/admin only), retention 0–90 shorten only, holds, deletion request |
| Operator console | Blocked run → fix → resume → reconcile; analysts get 403 on every console route |
| Accessibility and themes | Keyboard navigation, focus states, light and dark themes; no unreadable contrast |

## Part 11. Independent rerun (Gate H) and release (Gate I)

1. Reviewer clones at the reported commit on a different machine.
2. Runs Part 2, Part 3 and Part 4 end to end, plus three randomly chosen IDs from each of Parts 6 and 7.
3. Compares results with the agent's evidence records. Any mismatch reopens the item.

---

## Sign-off

### Gate summary

| Gate | Scope | Result | Evidence link | Reviewer | Date |
| --- | --- | --- | --- | --- | --- |
| Part 1 | Package and harnesses | | | | |
| Part 2 | Static checks, image scan | | | | |
| Part 3 | Clean install without key | | | | |
| Part 4 | Demo through real API | | | | |
| Part 5 | Live acceptance | | | | |
| Part 6 | DD-01 … DD-30 | | | | |
| Part 7 | D1 … D6 | | | | |
| Part 8 | Providers and security | | | | |
| Part 9 | Fault injection | | | | |
| Part 10 | UI journeys | | | | |
| Part 11 | Independent rerun | | | | |

### Decision status

| Decision | Decided | Specified | Implemented (SHA) | Tested (env, run link) | Verified (reviewer, date) |
| --- | --- | --- | --- | --- | --- |
| D1 External AI | 2026-11-07 | Yes | | | |
| D2 Retention | 2026-11-07 | Yes | | | |
| D3 Sanctions | 2026-11-07 | Yes | | | |
| D4 OCR | 2026-11-07 | Yes (harness passed, not product) | | | |
| D5 Licence | 2026-11-07 | Yes | | | |
| D6 False-claims site | 2026-11-07 | Yes | | | Pending deployment and verification |

### Blockers

| ID | Resolved? | How | Approved by |
| --- | --- | --- | --- |
| B1 Object store default | | | |
| B2 D6 repository and Pages | | | |
| B3 OFAC SDN host | | | |
| B4 Local model profile | | | |
| B5 Licences at pin | | | |

### Final verdict

| Question | Answer |
| --- | --- |
| Any automatic fail condition (F1–F11) hit? | |
| All release-blocking items (E2E-01 … E2E-25, PRV-01 … PRV-20) passed in `real`? | |
| Items left NOT_RUN or BLOCKED, with reasons | |
| Accepted for release? | |
| Signed | |
