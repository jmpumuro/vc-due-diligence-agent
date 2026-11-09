# Gap remediation addendum (due diligence)

This tab is the canonical list of remaining risks found in the due diligence gap analysis and the corrective requirement for each. The earlier addendum items (ledger, atomic budgets, provenance, version-bound review, lifecycle, sandboxed fetch, auth, readiness) are retained and live in the master plan; they are not repeated here. Every requirement below is specified only; none has been implemented or tested.

## Gap analysis summary

| # | Gap found in the research-agent plan | Risk | Corrective requirement | Canonical section |
| --- | --- | --- | --- | --- |
| G1 | One assessment depth only; no notion of screening vs diligence | Users read a light screen as diligence | Three explicit levels with prerequisites, availability table and per-level gates | Master plan › Diligence levels |
| G2 | Research organised by question, not by diligence domain | Coverage gaps invisible; no per-domain gate | Twelve `DomainModule`s with contracts and tests | Domain specification |
| G3 | Claim confidence and investment score could be read as one number | False certainty | Four separate measures (source reliability, claim confidence, evidence coverage, attractiveness); UI never combines them | Master plan › Findings and evidence standards |
| G4 | No finding classes | Inference shown as fact | Seven `Finding.kind` values, enforced at write time | Contracts › Finding |
| G5 | No private documents | Level 3 impossible | Data room with authorization, ClamAV, sandboxed parsers, envelope encryption, deal teams | Master plan › Private documents |
| G6 | Numbers produced by the LLM | Invented or wrong metrics | `ddcalc` deterministic engine; LLM may only propose extracted values that pass validation | Master plan › Financial analysis |
| G7 | No human correction for spreadsheets | Silent misreads | Financial validation queue with versioned corrections | Master plan › Private documents |
| G8 | Reports could change after approval | Audit failure | `ReportVersion` immutable; new evidence opens a new revision | Master plan › Due diligence report |
| G9 | No upgrade path | Duplicate work, lost history | `POST /assessments/{id}/upgrade` creates a revision that reuses frozen public evidence | Master plan › Diligence workflows |
| G10 | No legal/security checklists | Ad hoc coverage | Structured checklists with evidence requirements and disclaimers | Master plan › Legal, commercial and security review |
| G11 | Several domain tools named but without a concrete implementation | Unbuildable | Each tool mapped to a library or API | Provider & tool matrix |
| G12 | pgvector listed as default while embeddings were optional | Contradictory instructions | pgvector installed always; embeddings on in live mode with lexical fallback | Change log › Contradictions resolved |

## Remaining risks and corrective requirements

### R1. Private documents reaching the LLM provider

**Risk.** Level 3 sends extracted passages to the OpenAI API. That is a disclosure to a processor, which some funds or companies will not accept.

**Requirement (resolved by D1).** External AI processing of private documents is off by default. Model calls on private data use a verified local model, or OpenAI only after an owner or admin authorizes the specific categories and purposes; otherwise they are skipped and reported. Enforcement is in `PolicyEnforcedProvider` before every request, including embeddings, retries and background jobs, and fails closed. See the master plan, Approved decisions › D1, and tests D1-01 to D1-12.

### R2. Prompt injection in uploaded documents

**Risk.** A deck or spreadsheet contains text that tells the agent to rate the company highly or to reveal other data.

**Requirement.** Document text is passed only inside delimited data fields; agent system prompts state that document content is untrusted. Tool calls are restricted per agent, and no tool can read outside the current assessment's scope (enforced by RLS, not by the prompt). A heuristic and model-based injection detector flags passages; flagged passages are shown to the deal team and excluded from evaluation until reviewed. Red-team fixtures are part of the test suite.

### R3. Malicious or malformed files

**Risk.** Parser exploits, zip bombs, macro documents, XML entity attacks.

**Requirement.** Size limit (default 50 MB per file, 2 GB per data room), MIME sniffing with libmagic that must agree with the extension, ClamAV scan before any parsing, rejection of encrypted archives and macro-enabled formats (`.docm`, `.xlsm`, `.pptm`) by default, archive expansion limits (depth 2, 500 entries, 10× ratio), defusedxml for OOXML, and parsing and local OCR (D4) in `worker-docs` with no network, read-only root, memory and CPU limits and a per-file timeout. A file that fails is quarantined and never reaches the LLM.

### R4. Cross-workspace or cross-deal leakage

**Risk.** Private evidence surfaces in another assessment, another firm, logs or search.

**Requirement.** Row-level security on `firm_id` plus a deal-team check for private rows; separate MinIO prefix and data key per data room; private text never written to logs, traces or the outbox payload (IDs only); private evidence never used as a search query or sent to SearXNG; vector queries filter by assessment before similarity; deletion removes objects, extracted text, embeddings and cached prompts, and writes a tombstone to the audit log. Isolation tests run against two fixture firms.

### R5. Financial spreadsheets misread

**Risk.** Merged cells, hidden rows, wrong sign conventions, mixed currencies, fiscal-year offsets.

**Requirement.** Extraction produces a `FinancialTable` draft with a confidence per cell and a structural check (totals foot, periods contiguous, single currency or explicit FX). Any failed check sends the table to the validation queue. Calculations refuse unvalidated tables (`409 VALIDATION_REQUIRED`). Corrections are versioned with author and reason; the original extraction is kept.

### R6. Over-reliance on self-reported data

**Risk.** The deck's figures pass through as facts.

**Requirement.** Company-authored material is classified `source_supported` unless corroborated. The report shows the share of material findings that rest only on company-authored sources, per domain.

### R7. Output mistaken for professional advice

**Risk.** Legal, accounting or security sections read as certification.

**Requirement.** Fixed disclaimers on sections 10, 12 and 13 and on exports; a lint test fails the build if templates contain wording such as "compliant", "certified", "audited by" or "no legal issues" outside quoted source text.

### R8. Workflow history growth and non-determinism with many domains

**Risk.** Twelve domain children with follow-ups can exceed history limits; new domain versions break replay.

**Requirement.** One child workflow per domain; child uses Continue-As-New after a configured event count; domain module versions are pinned in the configuration version; code changes use `workflow.patched()` or worker versioning; replay tests run against recorded histories for each level.

### R9. Cost growth at Level 2 and Level 3

**Risk.** Twelve domains multiply search, fetch and model calls.

**Requirement.** Per-level and per-domain budgets reserved atomically before work starts; the planner degrades gracefully (fewer tasks per domain) instead of exceeding the budget; gates report `partial` when tasks were cut for budget, so the reason is visible.

### R10. Search blocking and outages

**Risk.** SearXNG upstream engines rate-limit or block; domains starve.

**Requirement.** Readiness and canary checks retained; domain tasks fall back to direct sources (registries, filings, company site, GitHub API); domains whose gates fail because search was unavailable are marked with reason `search_unavailable` and can be re-run without re-running the rest.

### R11. Personal data about founders and employees

**Risk.** Collecting more personal data than needed; GDPR exposure for the fund.

**Requirement.** Team domain collects professional history only; no protected attributes, family, health or social-media scraping; retention follows the workspace policy; a subject-access export and erasure path exists for people records.

### R12. Report export leakage

**Risk.** PDF or DOCX exports of Level 3 reports are forwarded.

**Requirement.** Level 3 exports carry a watermark with user and timestamp, are logged, and are only available to deal-team members. Public-only (Level 1 and 2) exports omit private sections entirely rather than redacting them.

## Acceptance for this addendum

This addendum is satisfied only when each R-item's tests in the testing tab have actually run and passed against the real services they name (not only fakes). Until then each item stays open in the change log.
