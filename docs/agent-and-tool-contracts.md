# Tool contracts

Every tool an agent can call, with its envelope, concrete schemas, permissions, errors and provider rules. Agents never open HTTP clients, browsers or hosted search calls directly. The Tool Registry validates each request and runs the tool as an Activity on its queue, and each call is a ledger operation.

## Envelope

```python
class ToolRequest(BaseModel):
    schema_version: Literal["1.0"]
    operation_id: UUID                 # stable across retries; ExternalOperationLedger key
    firm_id: UUID                      # from TenantContext, never from agent output
    assessment_id: UUID | None
    role: AgentRole                    # checked against the permission matrix
    tool_name: ToolName
    args: dict[str, Any]               # validated against the tool's own model before dispatch
    budget_ref: UUID | None            # BudgetReservation id
    deadline_at: datetime
    data_classification: Literal["public", "tenant_private"]

class ToolResult(BaseModel):
    schema_version: Literal["1.0"]
    operation_id: UUID
    status: Literal["succeeded", "partial", "unavailable", "blocked", "failed"]
    data_ref: ArtifactRef | None
    provenance_refs: list[UUID]        # snapshot_ids or search_record_ids
    provider: str
    latency_ms: int
    usage: ToolUsage                   # requests, bytes, billable_units, cost_usd, cost_certainty
    error_code: ToolErrorCode | None
    retryable: bool
    diagnostics: dict[str, str] = {}
```

## Concrete schemas

```python
class SearchRequest(BaseModel):
    query: str = Field(max_length=400)
    category: Literal["general", "news"] = "general"
    language: str | None = None
    time_range: Literal["day", "month", "year"] | None = None   # values SearXNG documents
    page: int = Field(1, ge=1, le=3)
    max_results: int = Field(20, le=50)

class SearchResult(BaseModel):
    search_record_id: UUID
    provider: Literal["searxng", "openai_web_search", "tavily", "brave", "exa", "fixture"]
    engine: str | None
    query: str
    title: str
    url: HttpUrl
    canonical_url: HttpUrl
    domain: str                        # registrable domain (public suffix list)
    snippet: str | None                # discovery metadata only, never evidence
    position: int
    language: str | None
    category: str | None
    published_at: date | None
    retrieved_at: datetime

class SearchResponse(BaseModel):
    state: Literal["ok", "degraded", "unavailable"]
    results: list[SearchResult]
    engines_responding: list[str]
    engines_failed: list[EngineFailure]   # name, reason: timeout | captcha | access_denied | too_many_requests | parse_error | suspended
    from_cache: bool

class FetchRequest(BaseModel):
    url: HttpUrl
    purpose: Literal["evidence", "discovery", "monitoring"]
    accept: list[Literal["html", "pdf", "feed", "text", "json"]] = ["html", "pdf", "text"]
    if_none_match: str | None = None
    if_modified_since: datetime | None = None
    allow_render_fallback: bool = False   # Research only; logged with a reason

class FetchResult(BaseModel):
    snapshot: SourceSnapshotMeta | None   # None when blocked or not modified
    not_modified: bool
    blocked_reason: Literal["robots", "policy", "ssrf", "content_type", "size", "auth_required", "paywall"] | None

class BrowserRenderRequest(BaseModel):
    url: HttpUrl
    reason: str                        # why plain fetch was insufficient
    wait_for: Literal["load", "networkidle"] = "load"
    timeout_s: int = Field(20, le=30)
    max_subrequests: int = Field(150, le=300)

class BrowserRenderResult(BaseModel):
    snapshot: SourceSnapshotMeta | None
    subrequests_made: int
    subrequests_blocked: list[BlockedRequest]   # url, reason (ssrf, policy, websocket, download)

class GitHubRequest(BaseModel):
    kind: Literal["org", "repo", "org_repos", "releases", "commits", "contributors", "search_repos"]
    owner: str | None = None
    repo: str | None = None
    query: str | None = None
    per_page: int = Field(30, le=100)
    page: int = Field(1, ge=1, le=10)
    etag: str | None = None

class GitHubResult(BaseModel):
    data_ref: ArtifactRef | None
    not_modified: bool
    rate_limit: RateLimitState         # limit, remaining, used, reset_at, resource
    outcome: Literal["ok", "not_found", "private_or_forbidden", "primary_limited", "secondary_limited"]

class FilingsRequest(BaseModel):     # SEC EDGAR
    cik: str | None = None
    company_name: str | None = None
    forms: list[str] = ["D", "S-1", "10-K", "8-K"]

class FeedRequest(BaseModel):
    feed_id: str | None = None         # from the feed registry
    url: HttpUrl | None = None
    etag: str | None = None
    last_modified: datetime | None = None

class FeedResult(BaseModel):
    items: list[FeedItem]              # guid, link, canonical_link, title, published_at, updated_at, summary (metadata only)
    not_modified: bool
    parse_warnings: list[str]

class EvidenceLookupRequest(BaseModel):
    assessment_id: UUID
    query: str | None = None
    claim_ids: list[UUID] = []
    subject: str | None = None
    limit: int = Field(20, le=50)      # no network; tenant enforced in SQL and RLS

class DiffRequest(BaseModel):
    previous_snapshot_id: UUID
    current_snapshot_id: UUID

class DiffResult(BaseModel):
    changed: bool                      # decided by normalized_sha256 comparison, never by a model
    previous_sha256: str
    current_sha256: str
    changed_spans: list[ChangedSpan]   # start, end, op (insert, delete, replace)
    change_ratio: float
```

**Data classification and scopes.** Search queries, fetch requests and results for an assessment are `tenant_private`: they show what a firm is researching. They are stored with `firm_id`, cached per tenant and never shared. Snapshot content of public pages is `public` and may be stored once and referenced by many tenants; the record that a tenant fetched it is private.

## Permissions

| Tool | Queue | Discovery | Planner | Research | Verification | Evaluation | Critic | Memo | Monitoring |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `web_search` | `q.fetch` | yes | — | yes | — | — | — | — | — |
| `fetch_url` | `q.fetch` | yes | — | yes | — | — | — | — | yes |
| `render_page` | `q.browser` | — | — | yes, with reason | — | — | — | — | — |
| `github_read` | `q.fetch` | — | — | yes | — | — | — | — | yes |
| `filings_read` | `q.fetch` | — | — | yes | — | — | — | — | yes |
| `rss_read` | `q.fetch` | yes | — | yes | — | — | — | — | yes |
| `evidence_lookup` | caller's queue (database only) | — | — | yes | yes | yes | yes | yes | yes |
| `diff_snapshots` | `q.monitoring` | — | — | — | — | — | — | — | yes |

Verification, Evaluation, Critic and Memo have no network tool. A request for a tool outside this matrix returns `POLICY_DENIED` and writes a security audit event.

## Error taxonomy

| Code | Meaning | Retry | Effect |
| --- | --- | --- | --- |
| `MISSING_CREDENTIALS` | A configured provider lacks its key | No | Provider disabled; console setup notice; default providers unaffected |
| `SEARCH_UNAVAILABLE` | Search service unreachable or circuit open for its whole window | No (circuit handles recovery) | `SourceGap`; RSS and direct sources continue |
| `SEARCH_DEGRADED` | Some or all upstream engines failed; partial or empty results | No | `SourceGap` naming failed engines; empty never means "no presence" |
| `SOURCE_BLOCKED` | robots, policy, SSRF, content type, size, paywall or login | No | Recorded with reason; no bypass |
| `SOURCE_NOT_FOUND` | 404 or 410 | No | Recorded; claim stays unverified |
| `RATE_LIMITED` | 429, or a provider's limit headers | After reset or `retry-after`, maximum 3 tries | Partial results kept |
| `TIMEOUT` | Deadline exceeded | Yes, 2 tries with jitter | Ledger may record `UNKNOWN` for billable providers |
| `INVALID_RESPONSE` | Malformed JSON or unexpected shape | Once | Diagnostics stored |
| `PARSER_FAILED` | HTML, PDF or feed could not be parsed | No | Raw snapshot kept |
| `BROWSER_FAILED` | Crash, hang or render cap hit | Once, in a fresh context | Other branches continue |
| `QUOTA_EXCEEDED` | Account or tenant quota | No | Setup or budget notice |
| `POLICY_DENIED` | Role, tenant or firm policy forbids the call | No | Security audit event |
| `PARTIAL_RESULTS` | Some pages or items missing | No | Coverage marks the missing part |
| `CIRCUIT_OPEN` | Provider circuit breaker open | No | Fast fail until half-open probe succeeds |

Agent-level codes in the main tab wrap these: a tool error inside a research task becomes a `SourceGap`, not an agent failure, unless every source for a must-question failed.

## SearXNG adapter

**Service settings (proposed; key names to verify against the deployed version).**

```yaml
# searxng/settings.yml, mounted read-only at /etc/searxng/settings.yml
use_default_settings: true
server:
  secret_key: "<generated at first start>"   # how the container injects it is UNVERIFIED
  limiter: false          # internal-only instance; app-level throttling below protects upstreams
  public_instance: false
  image_proxy: false
search:
  safe_search: 0
  autocomplete: ""
  formats: [html, json]   # json must be listed or the API returns 403
outgoing:
  request_timeout: 3.0
```

- **Engines:** the default engine set of the pinned SearXNG release, narrowed by an explicit allow-list in configuration. Which engines are enabled by default, and the exact allow-list syntax, are UNVERIFIED and must be recorded from the pinned release before Stage 2 closes.
- **Limiter:** off, because the service sits only on the internal Compose network, no host port is published, and the application throttles every query. If anyone exposes the instance, the limiter and Valkey must be turned on first; startup fails if a host port is mapped while `limiter: false`.
- **Readiness versus function:** the Compose health check asks for `format=json` on a fixed query and requires a 200 with parseable JSON. A separate canary runs hourly (and on demand from the console) with a benign query, and requires at least 3 results with `http(s)` URLs. Readiness can pass while the canary fails; that is the `degraded` state.
- **Throttling:** a global token bucket of 1 query per second (burst 3), at most 4 concurrent queries, a per-tenant daily cap (default 500), and 2 retries with jitter on timeout only. Upstream 403 or 429 responses are reported by SearXNG as engine suspensions; the adapter does not retry them. A circuit breaker opens after 5 consecutive unavailable responses and probes again after 60 seconds.
- **Normalization:** lower-case scheme and host, IDNA host, remove default ports and fragments, drop tracking parameters (`utm_*`, `gclid`, `fbclid`, `mc_cid`, `ref`), sort the remaining query parameters, and remove the trailing slash except at the root. Results are deduplicated by canonical URL, keeping the best position and listing every engine that returned it, and grouped by registrable domain. Each query is stored with provider, engine, position and time, for provenance.
- **Safety:** titles and snippets are untrusted text; they enter prompts only as data blocks, never in instructions. URLs pass the SafeFetcher checks before any fetch.
- **Cache:** a PostgreSQL table keyed by `(firm_id, provider, normalized query, category, language, time_range, page, engine-set version)`, 6 hours for general search and 1 hour for news.
- **Fallback:** none by default. A firm may configure a fallback provider per capability; a billable fallback also needs `allow_billable_fallback: true` and shows in usage as a separate cost line.

## GitHub adapter

Unauthenticated by default (60 requests/hour per IP); `GITHUB_TOKEN` is optional. The adapter sends `If-None-Match` with stored ETags, reads the `x-ratelimit-*` headers on every response, and stops calling until `x-ratelimit-reset` when `remaining` reaches 0. For secondary limits it waits for `retry-after` when present, otherwise at least 60 seconds, then backs off exponentially for at most 3 tries. Outcomes distinguish not found, private or forbidden, primary limit and secondary limit. GitHub data supports team and product claims; it never supports revenue, adoption or product-market-fit claims on its own.

## Feeds and filings

- **Feeds:** each feed in the registry has an owner, refresh interval, ETag and Last-Modified state, and parser diagnostics. Items are deduplicated by GUID, then by canonical link. Publication and retrieval dates are kept separately, edited items create a new version, and deleted items are marked, not removed.
- **EDGAR:** requests send the configured `EDGAR_USER_AGENT` (company name and admin email), are throttled to 5 per second by default against the SEC's published maximum of 10, and use the `data.sec.gov` JSON APIs.

## Adding a provider

Implement the capability protocol (`SearchProvider`, `Fetcher`, `Renderer`, `StructuredSource` or `FeedSource`), declare its capabilities and credential requirements, add a source policy file, register it in configuration, and pass the shared provider contract tests and the provider test template. No agent or workflow code changes.

## Due diligence contracts

These models extend the tool and agent contracts above for the VC Due Diligence Agent. `Finding` and `CalculationResult` are defined in the master plan; domain modules are defined in the domain specification tab. All models are Pydantic v2, frozen once persisted, and carry `firm_id`, `assessment_id` and `revision` where they belong to an assessment.

### Shared types

```python
Recommendation = Literal["advance", "hold", "pass", "inconclusive"]
# Legacy values are mapped when old rows are read and by migration 0051: "watch" -> "hold", "insufficient_evidence" -> "inconclusive".
# "advance" may carry conditions; the UI shows "Advance, with conditions" and lists them.

FindingKind = Literal["verified_fact", "source_supported", "derived_calculation", "inference",
                      "contradictory", "missing", "unresolved_risk"]

GateResult = Literal["sufficient", "partial", "insufficient", "not_applicable", "unavailable_at_level"]

Stage = Literal["planning", "ingesting_documents", "domains_running", "awaiting_validation", "follow_up_research",
                "domain_gates", "cross_domain_check", "evidence_freeze", "evaluating", "critiquing",
                "report_writing", "report_ready"]

class SourceReliability(BaseModel):
    label: Literal["strong", "good", "fair", "weak"]
    independent_share: Decimal         # share of material findings with at least one independent source
    company_only_share: Decimal        # share resting only on company-authored material

class ClaimConfidence(BaseModel):
    label: Literal["high", "medium", "low"]
    verified: int
    source_supported: int
    inference: int

class EvidenceCoverage(BaseModel):
    domains_sufficient: int
    domains_partial: int
    domains_insufficient: int
    domains_not_run: int               # not_applicable + unavailable_at_level

class Attractiveness(BaseModel):
    score: Decimal | None              # 1-5 weighted rubric score; None when inconclusive
    range: tuple[Decimal, Decimal] | None
    advance_threshold: Decimal

class Measures(BaseModel):              # four measures, never combined into one number
    source_reliability: SourceReliability
    claim_confidence: ClaimConfidence
    evidence_coverage: EvidenceCoverage
    attractiveness: Attractiveness

class DomainStatusSummary(BaseModel):
    domain_id: DomainId
    status: Literal["pending", "running", "complete", "partial", "failed", "skipped"]
    gate_result: GateResult
    reason: str | None
    sources_found: int
    sources_required: int
    findings: int
    contradictions: int
    risks: int
    requests: int
    can_retry: bool

class Progress(BaseModel):
    stage: Stage
    domains_complete: int
    domains_total: int
    documents_ready: int | None = None
    documents_total: int | None = None
```

### Supporting types

These were referenced above but not spelled out before 2026-11-07. The complete Pydantic transcription, used to validate the fixture set, is `project/fixtures/models.py` in the design prototype; the definitions below are canonical.

```python
AssessmentState = Literal["CREATED", "PLANNING", "RESEARCHING", "VALIDATING", "EVALUATING", "CRITIQUING", "MEMO_READY",
                          "AWAITING_REVIEW", "INFORMATION_REQUESTED", "DELIVERING", "COMPLETED", "REJECTED",
                          "BLOCKED_CONFIGURATION", "BUDGET_EXHAUSTED", "CANCELLED", "FAILED"]

class PeriodRange(BaseModel):
    start: date
    end: date                          # >= start
    granularity: Literal["month", "quarter", "year", "point"]

class SheetLocator(BaseModel):    kind: Literal["sheet"];     sheet: str; cell: str      # A1 notation or range
class PageLocator(BaseModel):     kind: Literal["page"];      page: int; bbox: tuple[Decimal, Decimal, Decimal, Decimal] | None
class SlideLocator(BaseModel):    kind: Literal["slide"];     slide: int
class ParagraphLocator(BaseModel): kind: Literal["paragraph"]; paragraph: int

class InputRef(BaseModel):         # one traced input to a calculation; must reference a table, document or claim
    name: str
    value: Decimal
    unit: str
    period: PeriodRange
    financial_table_id: UUID | None = None
    table_version: int | None = None
    document_id: UUID | None = None
    document_version: int | None = None
    locator: SheetLocator | PageLocator | SlideLocator | ParagraphLocator | None = None
    claim_id: UUID | None = None

class FinancialCell(BaseModel):
    period: PeriodRange
    value: Decimal | None
    raw: str                           # text exactly as read
    locator: SheetLocator | PageLocator
    confidence: Decimal                # 0-1, extraction confidence

class FinancialRow(BaseModel):
    line: str
    is_total: bool = False
    total_of: list[str] = []
    total_rule: Literal["sum", "rollforward"] | None = None   # rollforward: total[i] = total[i-1] + sum(parts[i])
    cells: list[FinancialCell]

class TableCheck(BaseModel):
    check: Literal["foots", "contiguous_periods", "single_currency", "sign_convention", "low_confidence_cells"]
    passed: bool                       # "foots" is recomputed by the server, never taken from the parser
    detail: str | None = None

class Correction(BaseModel):
    correction_id: UUID
    author: UUID
    line: str
    period_start: date
    old_value: Decimal | None
    new_value: Decimal
    reason: str                        # required, min 3 characters
    at: datetime

class ScorecardRow(BaseModel):     # attractiveness breakdown
    criterion_id: str
    score: int | None                  # 1-5
    weight: Decimal
    facts_count: int
    evidence_strength: Literal["strong", "good", "mixed", "weak"]
    rationale: str
    revised_after_critique: bool
    finding_ids: list[UUID]

class OverrideCondition(BaseModel):
    stage: list[str] | None = None
    industry: list[str] | None = None
    geography: list[str] | None = None
    thesis_tag: list[str] | None = None

class DomainConfigSet(BaseModel):  # body of GET and PUT /config/domains
    config_version: int
    domains: list[DomainConfig]        # all 12, once each; thesis_fit cannot be disabled (422 DOMAIN_REQUIRED)
```

JSON wire format: `Decimal` values are strings, dates ISO 8601, `min_sources` and `task_budget` keys are the level as a string ("1", "2", "3").

### Planning and execution

```python
Level = Literal[1, 2, 3]

class DomainPlan(BaseModel):
    assessment_id: UUID
    revision: int
    level: Level
    domain_id: DomainId
    module_version: str                       # "traction@1"
    questions: list[ResearchQuestion]          # existing model, now tagged with domain_id
    required_claim_types: list[str]
    gate: GateThresholds                       # min_sources, required items, per level
    task_budget: int
    budget_reservation_id: UUID

class DiligenceTask(BaseModel):
    task_id: UUID
    domain_id: DomainId
    kind: Literal["search", "fetch", "render", "filing", "github", "feed",
                  "document_lookup", "table_extract", "checklist_item", "calculation",
                  "sanctions_check", "dns_tls_check"]
    input: dict                                # validated against the tool's input schema
    evidence_scope: Literal["public", "private"]
    idempotency_key: str                       # "{assessment}:{revision}:{domain}:{task_hash}"
    attempt_limit: int = 3

class DomainAssessment(BaseModel):
    assessment_id: UUID
    revision: int
    domain_id: DomainId
    status: Literal["pending", "running", "complete", "partial", "failed", "skipped"]
    gate_result: Literal["sufficient", "partial", "insufficient", "not_applicable", "unavailable_at_level"]
    gate_reasons: list[str]                    # e.g. "search_unavailable", "budget_cut", "no_private_documents"
    coverage: Coverage                         # sources found vs required, per claim type
    finding_ids: list[UUID]
    calculation_ids: list[UUID]
    risk_ids: list[UUID]
    contradiction_ids: list[UUID]
    information_request_ids: list[UUID]
    company_authored_share: Decimal            # share of material findings resting only on company sources
    summary: str                               # Memo Agent text, cites finding_ids only
```

### Risks, scenarios, requests

```python
class RiskItem(BaseModel):
    risk_id: UUID
    assessment_id: UUID
    domain_ids: list[DomainId]
    title: str
    description: str
    severity: Literal["critical", "high", "medium", "low"]
    likelihood: Literal["likely", "possible", "unlikely", "unknown"]
    finding_ids: list[UUID]                    # at least one
    mitigation_question: str | None
    status: Literal["open", "accepted", "mitigated", "closed"]
    owner_user_id: UUID | None
    access: Literal["workspace", "deal_team"]

class Assumption(BaseModel):
    name: str
    value: Decimal
    unit: str
    basis: Literal["cited", "user_entered", "inference"]
    finding_ids: list[UUID] = []

class Scenario(BaseModel):
    scenario_id: UUID
    name: Literal["bear", "base", "bull"] | str
    assumptions: list[Assumption]
    calculation_ids: list[UUID]                # ddcalc outputs: ownership at exit, multiple

class InformationRequest(BaseModel):
    request_id: UUID
    assessment_id: UUID
    domain_id: DomainId
    requested_item: str                        # "Monthly management accounts, last 24 months"
    reason: str                                # which gate or calculation needs it
    blocking: bool                             # true if a required gate depends on it
    status: Literal["draft", "sent", "received", "waived", "closed"]
    linked_document_ids: list[UUID] = []
    created_by: Literal["system", "user"]
```

Requests are drafted by the system and marked `sent` by a person; the system never contacts the company itself. A founder-facing portal is deferred.

### Documents and financial tables

```python
class DocumentVersion(BaseModel):
    document_id: UUID
    version: int
    assessment_id: UUID
    filename: str
    declared_mime: str
    detected_mime: str                         # libmagic
    size_bytes: int
    sha256: str
    status: Literal["uploaded", "scanning", "rejected", "quarantined", "parsing",
                    "classified", "needs_validation", "ready", "failed"]
    reject_reason: str | None
    classification: DocClass | None            # pitch_deck, financials, cap_table, contract, policy, board_material, other
    classification_source: Literal["model", "user"] | None
    parser: str | None                         # "pypdf@x", "pdfplumber@x", "python-docx@x", "openpyxl@x"
    page_count: int | None
    injection_flags: int = 0
    uploaded_by: UUID
    object_key: str                            # encrypted object in the data-room bucket
    key_id: str                                # wrapped data key reference

class DocumentSpan(BaseModel):                 # private counterpart of EvidenceSpan
    span_id: UUID
    document_id: UUID
    version: int
    locator: PageLocator | SheetLocator | SlideLocator | ParagraphLocator
    text: str                                  # exact extracted text
    text_sha256: str
    extraction_method: Literal["native_text", "native_table", "ocr"]       # D4
    ocr_engine: str | None = None              # "tesseract@5.3.4"
    ocr_language: str | None = None            # "eng"
    ocr_confidence: Decimal | None = None      # mean word confidence of the page, 0-100
    ocr_reason: Literal["native_chars_low", "garbled_text_layer", "image_dominated"] | None = None
    low_confidence: bool = False               # ocr_confidence < 60 -> findings capped at claim_confidence=low

class FinancialTable(BaseModel):
    financial_table_id: UUID
    version: int
    document_id: UUID
    statement: Literal["income", "balance", "cash_flow", "kpi", "cap_table", "customer_revenue", "pipeline"]
    currency: str | None
    periods: list[PeriodRange]
    rows: list[FinancialRow]                   # each cell keeps its source SheetLocator and extraction confidence
    checks: list[TableCheck]                   # foots, contiguous_periods, single_currency, sign_convention
    status: Literal["draft", "needs_validation", "validated"]
    validated_by: UUID | None
    corrections: list[Correction] = []         # author, cell, old, new, reason, at
```

### Report

```python
class ReportSection(BaseModel):
    number: int                                # 1..21
    key: str                                   # "executive_summary" ... "evidence_appendix"
    status: Literal["supported", "incomplete", "not_applicable", "unavailable_at_level"]
    status_reason: str | None
    body_md: str                               # every sentence carries [finding:<id>] or [calc:<id>] markers
    finding_ids: list[UUID]
    access: Literal["workspace", "deal_team"]

class ReportVersion(BaseModel):
    report_version_id: UUID
    assessment_id: UUID
    revision: int
    level: Level
    schema_version: str = "ddreport@1"
    evidence_snapshot_set_id: UUID
    recommendation: Recommendation
    conditions: list[str] = []
    measures: Measures                         # source_reliability, claim_confidence, coverage, attractiveness — kept separate
    sections: list[ReportSection]              # exactly 21, in order
    disclaimers: list[str]
    created_at: datetime
    approved_by: UUID | None                   # set once; approval never edits content
```

The JSON export is `ReportVersion.model_dump(mode="json")`, with deal-team sections removed for viewers outside the deal team. A JSON Schema is generated from the model and published at `/schemas/ddreport@1.json`, and a contract test checks that it has not changed without a version bump.

### Tools added for due diligence

| Tool | Input → output | Implementation | Queue | Scope |
| --- | --- | --- | --- | --- |
| `document_lookup` | `{query, document_ids?, classes?}` → `DocumentSpan[]` | PostgreSQL full-text plus pgvector over the assessment's own spans | `q.docs` | Private, deal team only |
| `document_ingest` (internal activity chain) | upload → `DocumentVersion` | libmagic → ClamAV → parser → classifier | `q.docs` | Private |
| `table_extract` | `{document_id, version, sheet? page?}` → `FinancialTable` draft | openpyxl (values, not formulas re-evaluated), pdfplumber tables, Python `csv` | `q.docs` | Private |
| `ddcalc` | `{metric, inputs: InputRef[]}` → `CalculationResult` | Pure Python, `Decimal`, versioned formulas | `q.docs` | Inherits inputs' scope |
| `checklist_review` | `{checklist_id, item_id}` → `LegalChecklistItem` | Retrieval over spans plus Verification Agent rubric | `q.verification` | Public or private |
| `sanctions_check` | `{names[], countries[]}` → matches | D3: official OFAC SDN and consolidated non-SDN datasets (versioned, hashed, XSD-validated), refreshed daily by `SanctionsIngestWorkflow`; RapidFuzz matching after `anyascii` normalization; returns `ScreeningRun` with potential matches for human review, never a sanctions determination. EU, UK and UN sources optional and off by default | `q.verification` | Public |
| `dns_tls_check` | `{domain}` → records, certificate, protocol, headers | dnspython and the standard `ssl` module, one TLS handshake and one GET of the homepage through the egress proxy; no port scanning | `q.fetch` | Public |
| `filings_read` (extended) | adds Form D and financial data endpoints | SEC EDGAR APIs with declared User-Agent; Companies House API (free key, optional) | `q.fetch` | Public |
| `github_profile` | `{login}` → profile and public repos | GitHub REST API (existing adapter) | `q.fetch` | Public |

### Permissions added

| Agent | New tools allowed |
| --- | --- |
| Research Planner | none (plans only) |
| Research Agent | `document_lookup`, `table_extract`, `filings_read` (Form D), `github_profile`, `dns_tls_check` |
| Verification Agent | `document_lookup`, `checklist_review`, `sanctions_check`, `ddcalc` |
| Evaluation Agent | `ddcalc` (scenarios only), read findings |
| Critic Agent | read findings, contradictions and risks; may request one follow-up round per domain |
| Memo Agent | read findings, calculations and section statuses; no retrieval tools |
| Monitoring Agent | `sanctions_check` list refresh, `filings_read`, `rss_read` |
| Discovery Agent | unchanged |

Any private-scope tool call checks deal-team membership in the activity itself, before reading data, and fails with `POLICY_DENIED` otherwise. Any model call that includes private segments is additionally decided by `PolicyEnforcedProvider` under D1 and fails with `EXTERNAL_AI_NOT_AUTHORIZED` when no allowed private route exists. `web_search` and `fetch_page` refuse private-derived queries and URLs with `PRIVATE_DATA_EGRESS_BLOCKED`.

### Error codes added

| Code | Retry | Meaning |
| --- | --- | --- |
| `UNSUPPORTED_FORMAT` | No | MIME or extension not on the allow-list |
| `MIME_MISMATCH` | No | Detected type differs from extension |
| `MALWARE_DETECTED` | No | ClamAV positive; object quarantined |
| `SCANNER_UNAVAILABLE` | Yes, backoff | clamd not responding; upload stays `scanning` |
| `PARSE_FAILED` | Once, with fallback parser | Parser error or timeout |
| `ENCRYPTED_DOCUMENT` | No | Password-protected file; user must upload an unencrypted copy |
| `LIMIT_EXCEEDED` | No | Size, page, archive or entry limit |
| `VALIDATION_REQUIRED` | No | Calculation requested on an unvalidated table |
| `NOT_COMPUTABLE` | No | Inputs missing; returned inside `CalculationResult`, not raised |
| `EXTERNAL_AI_NOT_AUTHORIZED` | No | Model call with private segments and no allowed private route (D1); step skipped and reported |

## Security and data-handling contracts (D1–D4)

The master plan's Approved decisions section is canonical for behaviour; these are the additional types. `ExternalAIPolicy`, `LocalModelConfig`, `RetentionRecord`, `SanctionsDataset`, `SanctionsEntry`, `ScreeningSubject`, `PotentialMatch` and `ScreeningRun` are defined there.

```python
class ModelInputSegment(BaseModel):          # D1: built by the Context Assembler, checked by PolicyEnforcedProvider
    text: str
    scope: Literal["public", "private"]
    category: PrivateDataCategory | None     # required when scope == "private"
    document_id: UUID | None = None
    document_version: int | None = None

class ModelRequestEnvelope(BaseModel):       # D1: the only input PolicyEnforcedProvider accepts
    workspace_id: UUID
    assessment_id: UUID | None
    revision: int | None
    purpose: AIPurpose
    segments: list[ModelInputSegment]
    operation_id: UUID                       # ledger link; retries reuse it and are re-checked
    public_only_variant_allowed: bool = False

class PolicyDecision(BaseModel):             # D1
    allowed: bool
    route: Literal["external", "local", "denied"]
    policy_version: int
    reason: str | None                       # e.g. "category document_tables not allowed"

class ExternalTransmission(BaseModel):       # D1 audit row, never content
    transmission_id: UUID
    workspace_id: UUID
    assessment_id: UUID | None
    revision: int | None
    policy_version: int
    provider: Literal["openai"]
    model: str
    purpose: AIPurpose
    categories: list[PrivateDataCategory]
    segment_count: int
    char_count: int
    payload_sha256: str
    operation_id: UUID
    at: datetime

class RetentionExtension(BaseModel):         # D2: at most one per data room
    extended_by: UUID
    reason: str
    new_delete_after: datetime               # <= reopened_at + 90 days
    at: datetime

class LegalHold(BaseModel):                  # D2
    hold_id: UUID
    data_room_id: UUID
    placed_by: UUID
    reason: str
    external_reference: str
    placed_at: datetime
    released_by: UUID | None = None
    released_at: datetime | None = None

class DeletionCertificate(BaseModel):        # D2 audit record kept after deletion
    data_room_id: UUID
    assessment_id: UUID
    trigger: Literal["retention", "request", "tenant_deletion"]
    retention_policy_version: int
    first_closed_at: datetime | None
    delete_after: datetime | None
    document_count: int
    total_bytes: int
    objects_deleted: int                     # all versions and delete markers
    rows_deleted: dict[str, int]             # table -> count
    data_key_destroyed_at: datetime
    verification: dict[str, bool]            # objects_empty, rows_zero, vectors_empty, fulltext_empty
    deleted_at: datetime
    crypto_erasure_complete_at: datetime     # deleted_at + BACKUP_RETENTION_DAYS
    actor: UUID | Literal["system"]

class OcrPageResult(BaseModel):              # D4: stored with the document version
    page_number: int
    method: Literal["native_text", "ocr", "ocr_skipped_limit", "ocr_failed"]
    reason: Literal["native_ok", "native_chars_low", "garbled_text_layer", "image_dominated"]
    native_chars: int
    image_coverage: Decimal
    ocr_engine: str | None = None
    ocr_language: str | None = None
    ocr_confidence: Decimal | None = None
    seconds: Decimal | None = None
    error: str | None = None
```

**Enforcement invariants (tested in D1-01 to D1-12).**

1. No production module except `PolicyEnforcedProvider` imports `openai` or constructs an HTTP client for a model endpoint.
2. `ModelRequestEnvelope` is the only accepted input, and untagged text cannot be constructed (the validator rejects `scope="private"` without a category).
3. Temporal payloads never contain `ModelInputSegment.text` for private segments.
4. Logs, traces and the ledger contain no private segment text.
5. A denied decision is final for that operation and is not retried externally.
