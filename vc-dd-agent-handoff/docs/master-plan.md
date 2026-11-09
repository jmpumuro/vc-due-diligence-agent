# Open-Source VC Due Diligence Agent — Master Implementation Plan

Nov 7, 2026 · @Joe

## Overview

**Product.** The Open-Source VC Due Diligence Agent is an open-source, self-hostable AI application that performs evidence-grounded venture capital due diligence, evaluates companies against configurable investment theses, identifies material risks and evidence gaps, produces auditable investment reports, and supports human investment decisions and ongoing monitoring. It works at three depths: Level 1 initial screening, Level 2 public due diligence, and Level 3 enhanced due diligence with authorized private documents. Public-source findings are never presented as equivalent to verified private financial, legal or commercial diligence. "Thesis" is the default name shown in the user interface and can be changed.

**Architecture.** Eight logical agents run as Python components behind Temporal Activities, sharing one run envelope, typed Pydantic v2 contracts and orchestrator-enforced budgets. Twelve diligence domains are typed, configurable modules executed by those same agents and by deterministic components (document parsers, the financial calculation engine, validators); they are not separate autonomous agents. Agents never call each other directly; workflows pass stable artifact references, and the evidence store is the only shared memory.

**Where each requirement lives.** One canonical place per topic; other places link to it.

| Topic | Canonical source |
| --- | --- |
| Product scope, levels, workflows, evidence standards, private documents, financial methods, report structure, deployment | This tab (Master plan) |
| Agent and tool contracts, schemas, permissions, error taxonomy, report schema | Agent & tool contracts tab |
| The twelve diligence domains | Domain specification tab |
| Providers, libraries, licences, credentials | Provider & tool matrix tab |
| Test cases and acceptance criteria | Testing & acceptance tab |
| Remaining risks and corrective requirements | Gap remediation tab |
| What changed and open decisions | Change log tab |
| User interface | Thesis UI — Implementation Prompt (separate doc) |

Earlier versions of this plan described a "VC Research Agent" producing screening memos. That scope is now Level 1; terms are mapped in the Change log (memo → report, screening → assessment at a chosen level). Requirements from those versions remain in force unless the Change log marks them modified or deferred.

**Amended 7 Nov 2026 by the Implementation Gap Remediation & Verification Addendum.** The eight-agent product, the Temporal architecture and the typed contracts stay. Where this plan and the addendum differed, the addendum's more explicit correction was taken and each one is marked with its addendum ID (P0-01 … P1-10) so it can be traced to an ADR. The main changes:

- Workflow identity is now per assessment, not per configuration version; idempotency keys are tenant- and fingerprint-scoped.
- Provider calls are at-least-once. An operation ledger records every external effect, and unknown outcomes and possible duplicate spend are shown, never hidden.
- Budgets are reserved atomically across five levels with leases and reconciliation.
- Evidence offsets and hashes are checked syntactically, then support is checked semantically, as two separate steps.
- Agents keep shared middleware but run on separate capability queues with least-privilege tools.
- Review approves an exact `ReviewTarget` (revision, evidence snapshot, evaluation, memo, policy), not just a revision number.
- Docker Compose first run, readiness states, reconciliation, Temporal versioning, data lifecycle and tenant isolation are specified and tested.

IMPLEMENTED means code exists; only VERIFIED, with captured evidence for every applicable gate, counts as done. Default model IDs below are proposals that must be checked against the operator's OpenAI account at startup.

**Amended 7 Nov 2026 by the Provider & Tool Audit.** Agreed defaults, not to be reversed without a written tradeoff and the maintainer's approval:

- **Reasoning:** OpenAI, through the official SDK.
- **Search:** self-hosted SearXNG, started by Docker Compose, with no search account needed.
- **Fetching:** HTTPX with selectolax, and Playwright as a controlled fallback.
- **Default sources:** public sources only. No commercial data provider is required.
- **Demo workspace:** seeded in PostgreSQL and served by the real API to a seeded demo user; browsable without credentials. There is no separate demo code path (see Real integrations and the demo workspace).

Facts were checked against official documentation on 7 Nov 2026; anything not checked is marked UNVERIFIED in the supporting tabs (provider matrix, tool contracts, provider tests, correction report). No code has been run; every test status is NOT\_RUN.

Supporting tabs: Provider & tool matrix · Agent & tool contracts · Testing & acceptance · Change log

**Design rules every agent follows**

- One objective per agent, stated in its contract and its prompt version.
- Inputs and outputs are Pydantic models with `schema_version`; breaking changes bump the major version.
- Agents read only the context the Context Assembler gives them, scoped by `firm_id` and `assessment_id`.
- Source text is untrusted data. It is wrapped, never concatenated into instructions.
- Every material claim in an output carries `evidence_ids[]` or an explicit unverified, not-publicly-verifiable or source-unavailable status.
- Large outputs go to object storage; the Activity returns a reference and a hash.
- Each run writes an `AgentExecution` row with model, prompt version, tokens, cost, latency and outcome.

## Diligence levels

Every assessment runs at one level, chosen at creation and recorded on every report. A higher level can reuse the frozen evidence of a lower one but never inherits its conclusions without re-verification.

|  | Level 1 — Initial screening | Level 2 — Public due diligence | Level 3 — Enhanced due diligence |
| --- | --- | --- | --- |
| Purpose | Decide whether further diligence is worth it | Deep, source-backed investigation of every applicable domain from permitted public sources | Combine public research with authorized private materials |
| Prerequisites | Company name or domain; active thesis | Same; Level 2 enabled in firm configuration | A Level 2 assessment (run first automatically if absent), a deal team assigned, at least one private document uploaded. Model steps on private data additionally need an allowed private route under D1 (verified local model, or external processing explicitly authorized); without one they are skipped and reported. |
| Domains run by default | 1 Company, 2 Team, 3 Market, 4 Competition, 5 Product, 6 Traction (public), 8 Funding (public), 12 Thesis fit; risks noted, not investigated | All 12 that apply to the stage and industry; 7, 9 and 10 limited to public evidence | All 12, with private evidence where provided |
| Sources | Search, company site, news, RSS, GitHub, EDGAR | All Level 1 sources plus filings, registries, patents and court records where an adapter exists | Level 2 sources plus the assessment's private documents |
| Financial metrics | Only publicly reported figures, labelled as company statements | Same, plus public filings | Calculated by the deterministic engine from validated private data |
| Output | Screening report: Level 1 sections, recommendation for further diligence | Public due diligence report: all 21 sections, risk register, contradictions, confidence, open questions | Enhanced due diligence report: all 21 sections with private provenance, reconciliation, financial analysis, outstanding information requests |
| Proposed default budget | $2.50 per assessment | $15 per assessment | $40 per assessment (excluding document processing limits) |
| Who may start it | Analyst and above | Analyst and above | Partner, admin or owner |

All budget figures are provisional until re-derived from current model pricing (UNVERIFIED).

**Upgrades.** "Upgrade to Level 2" or "Upgrade to Level 3" opens a new revision of the same assessment with trigger `upgrade` and the new level. It reuses the previous revision's frozen evidence set as input and plans only the added domains and questions. Every reused claim is re-checked against the higher level's sufficiency gate. Approved reports of lower levels stay unchanged and readable.

**What a level never claims.** Level 1 and Level 2 reports state on every page that they rely on public sources only and do not verify private financial, legal or commercial facts. Level 3 reports state which domains had private evidence and which did not. No report is presented as legal advice, an audit, or a security certification.

## Shared agent runtime

Every agent is a subclass of `BaseAgent[InT, OutT]` and shares one execution middleware for budgets, tracing, ledger writes and persistence. Agent code only implements `plan_context()` and `execute()`. **Amended (P0-05):** there is no single `run_agent` Activity. Each capability class has its own Activity entry point and task queue, and each worker holds only the credentials its tools need.

| Capability class | Task queue | Agents / work | Network and write permissions |
| --- | --- | --- | --- |
| discovery | `q.discovery` | Discovery | Approved outbound web via SafeFetcher; write candidates |
| fetch | `q.fetch` | SafeFetcher, SearXNG client, GitHub, EDGAR and feed clients | Approved outbound web; write snapshots to object storage |
| research | `q.research` | Planner, Research | LLM provider; read snapshots; no direct web |
| verification | `q.verification` | Verification | LLM provider; read-only evidence |
| evaluation | `q.evaluation` | Evaluation, Critic, Memo | LLM provider; read-only evidence; write evaluation/memo artifacts |
| monitoring | `q.monitoring` | Monitoring, snapshot diff | LLM provider; read snapshots |
| delivery | `q.delivery` | CRM, notifications, webhooks | Only configured integration endpoints; outbox read |
| fixtures | `q.replay` (`--profile ops`) | Operator replay only, bound to `ReplayProvider` (responses recorded in a real run's ledger). Never used by the demo workspace or acceptance tests. | No network; read ledger artifacts; write like the role it replays |

A ninth queue, `q.browser`, is served only by `worker-browser` (Playwright with pinned Chromium) behind the egress proxy, so rendering never shares a process or network route with the other fetchers.

A tenth queue, `q.docs`, is served by `worker-docs`: document validation, parsing and extraction in a sandbox with no network, together with `ddcalc` calculations. Its workers can read the data room's encrypted objects and decrypt them with the data room key, and nothing else.

Queue names, routing, timeouts and retry policies live in validated configuration. Queues may be consolidated for small installs if the merge is recorded in an ADR and the permission tests still pass.

```python
class AgentSpec(BaseModel):
    role: AgentRole                    # discovery | planner | research | verification | evaluation | critic | memo | monitoring
    capability: CapabilityClass        # selects task queue + worker permission set (P0-05)
    prompt_ref: ImmutableRef           # "research@1.4.0" + sha256 of the rendered template
    model: ModelConfig                 # provider, model_id (verified at startup), temperature, max_output_tokens
    tools: list[ToolName]              # allow-list enforced outside the model by ToolRegistry
    budget: AgentBudget
    timeout_s: int
    max_iterations: int
    retry_safety: Literal["pure", "idempotent", "ledgered", "unsafe"]   # how retries are allowed (P0-02)
    schema_compat: Literal["backward", "full", "none"]               # checked before dispatch

class AgentBudget(BaseModel):
    max_input_tokens: int
    max_output_tokens: int
    max_cost_usd: Decimal
    max_tool_calls: int
    max_elapsed_s: int                 # tracked separately from money (P0-03)

class AgentRunRequest(BaseModel, Generic[InT]):
    schema_version: Literal["2.0"]
    operation_id: UUID                 # stable logical ID; identical across retries (P0-02)
    firm_id: UUID                      # copied from TenantContext, never from user input (P1-09)
    assessment: AssessmentIdentity | None
    config_snapshot_id: UUID           # immutable, pinned at assessment creation
    spec: AgentSpec
    input: InT
    context_scope: ContextScope        # firm_id + assessment_id + allowed artifact prefixes
    context_refs: list[ArtifactRef]    # authorized by ContextAssembler before dispatch
    reservation_id: UUID               # budget reservation held for this run (P0-03)
    trace: TraceContext                # traceparent, workflow_id, activity_id, attempt, task_queue

class AgentRunResult(BaseModel, Generic[OutT]):
    schema_version: Literal["2.0"]
    operation_id: UUID
    status: Literal["succeeded", "partial", "failed", "budget_exhausted", "blocked_configuration"]
    output: OutT | None
    output_ref: ArtifactRef | None     # set when output > 64 KB
    partial: PartialResult | None      # what is valid and reusable when status is partial/budget_exhausted
    usage: Usage                       # tokens, tool_calls, cost_usd, cost_certainty: actual | estimated | unknown
    warnings: list[AgentWarning]
    error: AgentError | None
    audit: AuditMeta                   # model_id, prompt_ref, provider_request_ids[], tool_calls[], timestamps
```

**Error taxonomy** — the Activity maps each to Temporal retry behaviour:

| Error code | Meaning | Handling |
| --- | --- | --- |
| `CREDENTIALS_MISSING` / `CREDENTIALS_INVALID` | No key, revoked or rejected key | Non-retryable. Assessment moves to `BLOCKED_CONFIGURATION`; resume action after fix (P1-04) |
| `PROVIDER_QUOTA_EXCEEDED` | Account quota or billing limit | Non-retryable; `BLOCKED_CONFIGURATION` with quota message |
| `PROVIDER_TIMEOUT` | Call exceeded its deadline; outcome may be unknown | Ledger marks `UNKNOWN`; bounded retry per provider policy, possible duplicate spend recorded |
| `PROVIDER_RATE_LIMITED` | 429 | Bounded backoff; retry hint read inside the Activity, which sleeps or raises with a computed `next_retry_delay` |
| `PROVIDER_UNAVAILABLE` | 5xx | Bounded exponential backoff, max 5; then `degraded` with partial results kept |
| `SCHEMA_VIOLATION` | Output failed validation after 2 repair attempts | Non-retryable |
| `BUDGET_EXHAUSTED` | A reservation could not be made or was used up | Non-retryable; partial output preserved |
| `TOOL_DENIED` | Tool or argument outside the allow-list | Non-retryable; security audit event |
| `SOURCE_BLOCKED` | SSRF, robots, terms or access-policy refusal | Non-retryable per URL; agent continues |
| `INJECTION_SUSPECTED` | Heuristic or classifier flag (defence in depth only) | Source quarantined from context; forbidden effects are prevented regardless (P1-02) |

Budgets, the operation ledger and retry semantics are specified in **Retry safety, operation ledger and atomic budgets** below. Model IDs are configuration, checked against the account's model list when the API starts; a missing model puts that role in `setup_required` instead of failing at run time.

**Model provider abstraction.** Agents never import a vendor SDK. They call an `LLMProvider`; swapping providers means adding one adapter and changing configuration.

```python
class LLMProvider(Protocol):
    name: str
    async def list_models(self) -> list[str]: ...                       # startup availability check
    async def complete(self, req: ProviderRequest) -> ProviderResponse: ...

class ProviderRequest(BaseModel):
    operation_id: UUID                 # forwarded as client metadata where the provider supports it
    model_id: str
    messages: list[Message]            # system/developer text from prompt_ref only; sources go in data blocks
    response_schema: dict              # JSON Schema of OutT; providers use native structured output when available
    max_output_tokens: int
    temperature: float | None
    timeout_s: int

class ProviderResponse(BaseModel):
    output_json: dict
    provider_request_id: str | None
    usage: Usage | None                # None -> cost_certainty "estimated"
    finish_reason: str
```

Shipped adapters:

- `OpenAIProvider`: the official Python SDK on the Responses API, with JSON-schema structured output. OpenAI's hosted `web_search` tool is never attached unless `SEARCH_PROVIDER=openai_web_search` is explicitly set, because it is billed separately and bypasses SafeFetcher provenance.
- `ReplayProvider`: serves responses recorded in a real run's ledger, for the operator's "Replay from ledger" tool only. `FakeLLMProvider`: unit tests only; it lives under `tests/` and an import-linter contract fails the build if any production entrypoint (api, workers, seed) can import it.

Prompts live in the repository as versioned templates; the system does not depend on OpenAI-hosted prompts, Agent Builder or Evals, which OpenAI's deprecations page lists for shutdown on 30 Nov 2026. Adapters map errors to the taxonomy above.

**Tool layer.** Agents request tools; they never open HTTP clients, browser sessions or hosted search calls themselves. The Tool Registry validates each `ToolRequest` (tool-specific Pydantic args, role permission, tenant scope, deadline, budget) and runs the tool as an Activity on its capability queue. It returns a `ToolResult` with a status of succeeded, partial, unavailable, blocked or failed, plus provenance references and a normalized error code.

Providers declare capabilities (`search`, `fetch`, `render`, `structured_api`, `feed`, `llm`) and their credential requirements, which are validated at startup and on every call. Fallback between providers happens only when configured, and never to a paid provider by default. Per-provider concurrency, retry with jitter, circuit breakers, timeouts and cancellation cleanup apply. Full schemas, the per-role permission matrix and the tool error taxonomy (`MISSING_CREDENTIALS`, `SEARCH_UNAVAILABLE`, `SEARCH_DEGRADED, SOURCE_BLOCKED`, `SOURCE_NOT_FOUND`, `RATE_LIMITED`, `TIMEOUT`, `INVALID_RESPONSE`, `PARSER_FAILED`, `BROWSER_FAILED`, `QUOTA_EXCEEDED`, `POLICY_DENIED`, `PARTIAL_RESULTS`, `CIRCUIT_OPEN`) are in the Tool contracts tab.

**Context assembly.** The Context Assembler builds each agent's input from authorized artifacts only: claims and spans for the assessment, the pinned configuration, prior revisions of the same assessment and, for deal-team runs at Level 3, the data room. **Vector search (reconciled):** pgvector is the default vector store, installed and migrated in every deployment. In live mode, public spans are embedded with OpenAI embeddings (model ID to verify at startup). Private spans are embedded only through an allowed private route under D1: the local embedding model, or OpenAI when external processing allows embedding\_inputs. The demo workspace's vectors are written to pgvector by the seed job like any other rows. Every query filters by `firm_id`, `assessment_id` and access scope before similarity, and PostgreSQL full-text ranking is always available as the fallback, so no feature depends on embeddings being present. The embedding model and dimensions are recorded per configuration version, and changing them triggers a background re-embed. Memory across assessments is limited to the firm's own public evidence about the same company; private evidence is never reused across assessments.

## Shared domain types

These models live in `vcra/domain/` and are imported by agents, workflows and the API. The frontend mirrors them in `web/lib/types.ts`, generated from the OpenAPI schema.

```python
class CompanyRef(BaseModel):
    company_id: UUID                   # stable canonical identity (P0-01)
    canonical_name: str
    primary_domain: str | None
    aliases: list[CompanyAlias] = []   # name/domain + source + confidence, auditable

# SourceSnapshotMeta and EvidenceSpan: see "Evidence provenance" below (replace SourceSnapshot / EvidencePassage)

VerificationStatus = Literal[
    "supported", "partially_supported", "unverified", "contradicted", "outdated",
    "not_publicly_verifiable",         # added in schema 2.0: private metric, never inferred
    "source_unavailable",              # added in schema 2.0: source deleted or taken down after capture
]

class Claim(BaseModel):
    claim_id: UUID
    subject: Literal["founder", "product", "market", "competitor", "traction", "funding", "team", "other"]
    statement: str
    value: ClaimValue | None           # typed number/money/date/enum with unit
    evidence_ids: list[UUID]
    provenance_valid: bool             # syntactic check: hashes, offsets, quote equality
    verification_status: VerificationStatus   # semantic check, separate and audited
    support_score: float               # 0-1, semantic entailment of claim by spans
    freshness_days: int | None
    contradiction_ids: list[UUID] = []
    extracted_by: UUID                 # agent_execution operation_id

class ResearchQuestion(BaseModel):
    question_id: str                   # "q.market.size"
    text: str
    required_evidence: list[str]       # e.g. ["tier1_source", "dated_within_365d"]
    priority: Literal["must", "should", "nice"]
    criterion_id: str                  # rubric criterion this question feeds (Key questions matrix)

class CoverageReport(BaseModel):
    per_question: dict[str, Literal["answered", "partial", "missing", "conflicting"]]
    coverage_score: float              # share of must-questions answered
    gaps: list[ResearchGap]
    source_gaps: list[SourceGap]       # tool, error_code (SEARCH_DEGRADED, SOURCE_BLOCKED, RATE_LIMITED...), affected question_ids

class ArtifactRef(BaseModel):
    artifact_id: UUID                  # resolved through an authorization check, never by key prefix alone (P1-09)
    sha256: str
    bytes: int
    media_type: str
```

Consumers of schema 1.x treat the two new statuses as `unverified`; this compatibility rule is tested.

**Persistence model.** All tables below carry `firm_id` and row-level security, except the shared public snapshot store, which is referenced by tenant rows and never queried directly by users.

| Entity | Key fields | Notes |
| --- | --- | --- |
| Firm, User, Membership | `firm_id`; `user_id`; `(firm_id, user_id, role)` | Roles below; one user can belong to several firms |
| Mandate, ConfigVersion | `mandate_id`; `config_version_id, number, scope, base_version_id` | Immutable once saved; assessments pin a `config_snapshot_id` |
| Company, CompanyAlias, IdentityResolution | `company_id`; alias + source + confidence; `request_id, candidates, status` | Names never merge companies on their own |
| Assessment, AssessmentRevision | `assessment_id, company_id, state, revision, trigger` | State machine enforced in the database |
| ResearchRun, StageSpan | `run_id`; `assessment_id, key, parent, started_at, ended_at, attempt, outcome` | StageSpan rows feed `/timeline` and the console Gantt |
| Source, SourceSnapshotMeta, EvidenceSpan | see Evidence provenance | Snapshots shared by reference across tenants |
| Claim, ClaimVerdict, Contradiction, EvidenceSnapshotSet | see domain types | A snapshot set is pinned by evaluation, memo and review |
| Evaluation, Critique, Memo | `evaluation_id, revision`; `critique_id`; `memo_version_id` | Immutable per version |
| ReviewTarget, Review, Decision | target digest; `review_id, decision, reviewer_id` | Decision rows are append-only |
| WatchlistEntry, MonitoringEvent | `entry_id, rules, paused`; `event_id, dedupe_key` |  |
| AgentExecution, ExternalOperation, BudgetReservation, BudgetLedger | see Retry safety section |  |
| IdempotencyKey, Outbox, Event | `(firm_id, endpoint, key)`; `outbox_id`; `event_id, sequence` | Events kept 72 hours |
| Notification, AuditEvent | `notification_id, user_id, read_at`; `audit_id, actor, action, subject, before, after` | Audit is append-only |

**Roles.** One role per membership; permissions are checked on the server for every endpoint and event stream.

| Capability | analyst | partner | operator | admin | owner |
| --- | --- | --- | --- | --- | --- |
| Read Research app, submit research, watch | yes | yes | no | yes | yes |
| Decide below the advance threshold | yes | yes | no | yes | yes |
| Decide at or above the advance threshold | no | yes | no | yes | yes |
| Edit thesis and rubric | no | yes | no | yes | yes |
| Agent console read; resume, rerun, acknowledge, reconcile | no | no | yes | yes | yes |
| Edit models, budgets, sources, review policy; cancel runs; budget overrides | no | no | no | yes | yes |
| Export tenant data, request deletion, manage members | no | no | no | no | yes |

**Deal teams.** Private evidence adds a second, per-assessment check on top of these roles. Partners, admins and owners can create a deal team and add analysts or partners to it. Only deal-team members may upload documents, open private findings, use the financial validation queue, and read or export Level 3 reports. Starting Level 3 requires partner, admin or owner. Operators never see private content.

Measures stay separate everywhere, including the UI: source reliability, claim confidence, evidence coverage and investment attractiveness (with its uncertainty range). Definitions and the evidence sufficiency gate are in **Findings and evidence standards**.

## Evidence provenance

A citation is valid only if the exact quoted text can be found again, byte for byte, in an immutable stored snapshot; whether it actually supports the claim is a second, separate judgement. Each capture produces two immutable artifacts — the raw response and the normalized text — each hashed and tagged with the normalizer version.

```python
class SourceSnapshotMeta(BaseModel):
    snapshot_id: UUID
    source_id: UUID
    url: HttpUrl
    raw_ref: str
    raw_sha256: str
    normalized_ref: str
    normalized_sha256: str
    normalization_version: str         # "norm@2.1": NFC, whitespace collapse, boilerplate strip
    captured_at: datetime
    content_type: str
    trust_tier: Literal[1, 2, 3]
    access_policy_id: str | None       # source adapter policy: terms, excerpt rights, retention (P1-07)
    requested_url: HttpUrl
    final_url: HttpUrl                 # after redirects
    redirect_chain: list[HttpUrl]
    http_status: int
    etag: str | None
    last_modified: datetime | None
    retrieved_by: Literal["httpx", "playwright", "github_api", "feed", "edgar", "fixture"]
    extractor: str                     # "selectolax-main@1.2", "pypdf@x", "feedparser@x"
    source_kind: Literal["company_controlled", "press_release_wire", "independent_journalism",
                         "aggregator", "syndicated_copy", "public_record", "code_repository", "other"]
    syndication_group: str | None      # same story across outlets, from normalized-text SimHash + canonical link

class EvidenceSpan(BaseModel):
    evidence_id: UUID
    snapshot_id: UUID
    char_start: int = Field(ge=0)      # Python code-point offset into normalized text
    char_end: int = Field(gt=0)        # exclusive
    quote: str
    published_at: date | None = None
```

**Syntactic validation** runs deterministically in an Activity, before any model sees the claim: the snapshot exists and belongs to the tenant's scope, both hashes match the stored objects, `char_end > char_start`, and `normalized_text[char_start:char_end] == quote`. Any failure sets `provenance_valid = false` and the claim cannot reach a finalized memo.

**Semantic validation** is the Verification Agent's job: does the span entail the claim with context, negation, units, dates and qualifiers intact. Its verdict and reasoning are stored as an audited record next to the syntactic result.

- Snapshots are never mutated. A changed page produces a new snapshot version; the old one stays valid for anything already pinned to it.
- Contradictions keep both claims and both sources; a preferred claim may be named, but nothing is overwritten.
- Every evaluation, critique, memo and review decision pins an `evidence_snapshot_id` (a set digest of the spans it used). New evidence produces a new snapshot set and a new assessment revision.
- A citation resolver maps `evidence_id` to URL, capture date and the excerpt the source's access policy allows to be displayed; excerpts outside that policy show the link only.

**Independent confirmation.** A claim counts as corroborated only by sources with different `syndication_group` values, and at least one source that is not `company_controlled` or `press_release_wire`. Syndicated copies of one press release count once. A company's own statement is labelled as such in the memo ("the company says"), even when many outlets repeat it.

**Search results are not evidence.** Titles, snippets and ranks from search are discovery metadata. A claim needs a span from a fetched, stored snapshot. If the original page cannot be fetched (403, 404, 429, robots, policy), the claim stays unverified and the gap is recorded; an inaccessible article never confirms a fact.

## Findings and evidence standards

Every material statement in a report is a `Finding` of exactly one class, and the class is shown next to it. A finding without provenance cannot be material.

| Class | Qualifies when | Shown as |
| --- | --- | --- |
| `verified_fact` | Supported by an authoritative primary record (filing, registry, court record, signed document), or by at least two independent sources (different `syndication_group`, at least one not company-controlled). At Level 3, private financial figures qualify only after validation and reconciliation | "Verified" |
| `source_supported` | Supported by a source but not independently corroborated, including everything the company says about itself | "The company says…" or "Reported by…" |
| `derived_calculation` | Output of the financial calculation engine from validated inputs | Value with formula and inputs one click away |
| `inference` | A judgement by the agents or an analyst, with the findings it rests on | "Inference", never phrased as fact |
| `contradictory` | Two or more findings conflict and the conflict is unresolved | Side-by-side comparison |
| `missing` | Evidence the gate requires is absent | "Not available" plus the information request |
| `unresolved_risk` | A risk is identified but evidence to confirm or mitigate it is pending | Risk register entry |

```python
class Finding(BaseModel):
    finding_id: UUID
    assessment_id: UUID
    revision: int
    domain_id: DomainId                # one of the twelve
    kind: Literal["verified_fact", "source_supported", "derived_calculation", "inference",
                  "contradictory", "missing", "unresolved_risk"]
    statement: str
    claim_ids: list[UUID] = []         # public or private claims with spans
    calculation_id: UUID | None = None
    based_on_finding_ids: list[UUID] = []   # required for inference
    claim_confidence: Literal["high", "medium", "low"]
    materiality: Literal["critical", "high", "medium", "low"]
    evidence_scope: Literal["public", "private", "mixed"]
    access: Literal["workspace", "deal_team"]   # private findings are deal-team only
```

**Provenance for every material finding.** Each cited claim resolves to a source URL or private document ID and version; the exact passage, page, slide or cell range; retrieval or upload time; snapshot hash; source type; and access restrictions. Public provenance is defined in Evidence provenance; private provenance in Private documents.

**Four measures, never combined.** Reports and the UI show these separately and never average them into one score:

- **Source reliability** — a property of each source: trust tier, `source_kind`, independence.
- **Claim confidence** — a property of each finding: support score, corroboration, freshness, validation state.
- **Evidence coverage** — a property of each domain: the share of required questions answered at the selected level.
- **Investment attractiveness** — the Evaluation output: rubric scores, thesis fit and scenarios, with its uncertainty range.

Attractiveness is computed only from domains that pass their sufficiency gate.

**Evidence sufficiency gate.** Each (level, domain) pair has a gate in configuration:

- the must-answer questions;
- the minimum independent sources for material findings;
- the required private document types (Level 3);
- the maximum evidence age.

The Verification Agent's output is checked against the gate deterministically and yields one gate result per domain: `sufficient`, `partial`, `insufficient`, `not_applicable` or `unavailable_at_level` (the same values as `DomainAssessment.gate_result`). An `insufficient` domain gets no score; its report section is marked `incomplete` and says "Inconclusive: insufficient evidence", listing what is missing. The recommendation becomes `inconclusive` when any domain the thesis marks as required is `insufficient`. The system states that a finding is inconclusive rather than fill the gap.

## Identity, submission and lifecycle

A company has one stable `company_id`; every intentional evaluation of it gets its own `assessment_id`, and the Temporal workflow ID is `dd:{firm_id}:{assessment_id}:r{revision}, one execution per revision (see Diligence workflows)` (P0-01). The earlier `screen:{firm_id}:{company_id}:{config_version}` ID is withdrawn because it blocked legitimate reassessment under an unchanged configuration.

- **Entity resolution** proposes candidate matches with a confidence score from domain, aliases and registry IDs. Names alone never merge companies; ambiguous matches get a provisional identity and a review task.
- **Assessment records** carry `firm_id`, `company_id`, `mandate_id`, an immutable `config_snapshot_id`, `revision`, `created_by` and a trigger: manual, discovery, monitoring or reassessment.
- **Sourcing does not wait for screenings.** `SourcingBatchWorkflow` dispatches each new company through an idempotent `start_screening` Activity that starts an independent workflow (ID conflict policy: use existing). No parent waits on human approval.

```python
class AssessmentIdentity(BaseModel):
    firm_id: UUID
    company_id: UUID
    assessment_id: UUID
    mandate_id: UUID
    config_snapshot_id: UUID
    revision: int = Field(ge=1)
    trigger: Literal["manual", "discovery", "monitoring", "reassessment", "upgrade", "new_evidence"]
    level: Literal[1, 2, 3]            # diligence level of this revision

class SubmissionPolicy(str, Enum):
    REUSE_ACTIVE = "reuse_active"        # default: attach to an in-flight assessment if one exists, else create
    NEW_ASSESSMENT = "new_assessment"    # always create, even with the same config
    REASSESS_LATEST = "reassess_latest"  # new revision of the latest completed assessment

class SubmitCompanyResponse(BaseModel):
    company: CompanyRef
    assessment_id: UUID
    outcome: Literal["created", "reused_active", "reassessment_created", "identity_review_required"]
    identity_candidates: list[IdentityCandidate] = []
    identity_request_id: UUID | None = None   # set with identity_review_required; resolve via POST /identity-resolutions/{id} within 24 h
```

**Idempotency keys** are scoped to (tenant, endpoint, key) and bound to a fingerprint of the normalized request body. They are written in the same database transaction that creates the assessment and expire after 24 hours.

| Request | Result |
| --- | --- |
| Same key, same fingerprint | Original response returned, no new work |
| Same key, different fingerprint | `409 IDEMPOTENCY_KEY_CONFLICT` |
| Two concurrent requests, same key | One wins via unique constraint; the other waits and receives the winner's response |
| No key, `reuse_active`, assessment running | Existing `assessment_id`, outcome `reused_active` |
| No key, completed assessment exists | New assessment only with `new_assessment` or `reassess_latest`; never implicit reuse |

&#91;embedded content: Assessment lifecycle · 15 states, 4 exception exits\]

All transitions are enforced by the database (a check on allowed from→to pairs) and mirrored in the workflow. Not every assessment enters review: a configured policy may route `out_of_mandate` results straight to Rejected with an audit event, and an agent's `recommendation` is only ever input to a human decision.

**Added for due diligence.** `INFORMATION_REQUESTED` follows `AWAITING_REVIEW` when the reviewer requests documents or answers. Revisions carry a `level` (1–3) and may have the triggers `upgrade` and `new_evidence`. Evidence freeze is a stage inside `VALIDATING`, not a state.

## Retry safety, operation ledger and atomic budgets

Activities run at least once, so the plan no longer claims exactly-once provider execution (P0-02). Every external effect gets a stable `operation_id`, derived from workflow ID, step key and input digest, never from the attempt number. That ID keys a row in the `ExternalOperationLedger`.

**Ledger states:** `RESERVED → IN_FLIGHT → SUCCEEDED | FAILED | UNKNOWN`, and `UNKNOWN → RECONCILED`. Transitions are compare-and-set updates on the row, each emitting an audit event.

| Retry finds | Action |
| --- | --- |
| `SUCCEEDED` with `result_ref` | Reuse the stored result; no provider call |
| `IN_FLIGHT` past its lease, or `UNKNOWN` | Provider policy: for OpenAI, re-issue the call and record `possible_duplicate_spend`; for CRM and webhooks, query the target by idempotency key before writing |
| `FAILED` (retryable) | New attempt under the same `operation_id` and reservation |
| `FAILED` (non-retryable) | Surface the error; no retry |

A database row cannot commit atomically with an OpenAI request, so the window between "request sent" and "result stored" is modelled explicitly as `IN_FLIGHT` with a lease. Usage is recorded with `cost_certainty`: `actual` (provider-reported), `estimated` (from token counts when the provider omitted usage) or `unknown` (call may have run but no response was received). No provider-side request deduplication is assumed; this limit is documented in the security and cost docs.

**Minimum ledger fields:** `operation_id`, `firm_id`, `assessment_id`, `activity_type`, `input_hash`, `provider`, `status`, `attempt_count`, `reservation_id`, `provider_request_id`, `result_ref`, `actual_cost`, `estimated_cost`, `cost_certainty`, `last_error`, `created_at`, `updated_at`. `operation_id` is unique; prompts and raw responses are stored as tenant-scoped artifacts, never in logs.

**Delivery effects** (CRM, notifications, webhooks, artifact writes) go through a transactional outbox: the event row commits with the business change, a dispatcher sends it with the event's idempotency key, and a unique constraint on the receiving side or a lookup-before-write stops duplicates. Temporal and PostgreSQL never share a transaction; the outbox is the bridge.

**Default delivery needs no external accounts.**

- **Notifications:** in-app by default. SMTP, generic webhook and Slack adapters are optional and need explicit configuration.
- **CRM:** a local JSON and CSV export of the approved memo, scores and citations, plus a signed, idempotent webhook interface. HubSpot and Salesforce adapters are optional, need explicit credentials, scopes and a field mapping, and are never mandatory.
- **Approval with nothing configured:** an approval with no adapter configured completes, with the memo downloadable and stored locally. It never triggers an unconfigured external write.

**Atomic hierarchical budgets (P0-03).** Limits exist at five levels: agent invocation, research task, assessment, tenant per day, and provider. Reservations are made in one PostgreSQL transaction that locks the affected ledger rows in a fixed order (provider → tenant → assessment → task) and fails if any level would go below zero.

```python
class BudgetReservation(BaseModel):
    reservation_id: UUID
    operation_id: UUID
    levels: list[BudgetLevelRef]       # every level the reservation draws from
    reserved: Spend                    # usd, input_tokens, output_tokens, tool_calls, elapsed_s
    settled: Spend | None
    status: Literal["held", "settled", "released", "expired", "reclaimed"]
    lease_expires_at: datetime         # renewed by Activity heartbeat
```

- The reservation is an upper bound: `max_output_tokens` × price plus the estimated input. If the model exceeds it, the overage is still settled as actual spend and the next reservation fails earlier.
- Settlement writes measured usage; unused funds return, already incurred costs never do. Unknown usage settles at the reserved amount with `cost_certainty = unknown` until reconciled.
- A reaper reclaims expired leases every minute; a reconciliation job compares ledger totals with provider usage reports daily.
- A quota lowered mid-run stops new reservations; held ones finish. `budget_exhausted` keeps every valid partial result and shows which research questions were left unanswered.
- Provider and per-domain rate limits are token buckets kept apart from money, so a rate-limited provider slows work without consuming budget.

**Continuing after `BUDGET_EXHAUSTED`.** An admin may apply a budget override (`POST /assessments/{id}/budget-overrides { limit_usd, reason }`), capped by the tenant's daily limit. The override is audited and opens a new revision with trigger `reassessment` that reuses all valid evidence from the stopped revision and plans only the unanswered questions. The stopped revision stays as it was.

## Agent specifications

Defaults below ship in `config/default.yaml` and are overridden per firm through a new configuration version. **Correction (provider audit):** the earlier defaults are withdrawn. `o4-mini` was shut down on 23 Oct 2026, and `gpt-4.1` and `gpt-4.1-mini` shut down on 14 Jan 2027, according to [OpenAI's deprecations page](https://developers.openai.com/api/docs/deprecations). The proposed IDs below are OpenAI's listed replacements. They are not final: the API checks them against the account's model list at startup, the quality harness must baseline them, and budgets must be re-derived from current pricing (UNVERIFIED). Tools are executed by the Tool Registry on the capability queues, never by the agent process; see the Tool contracts tab.

| Agent | Objective | Proposed model (verify at startup) | Tools | Timeout | Max iter. | Budget (USD, provisional) |
| --- | --- | --- | --- | --- | --- | --- |
| Discovery | Find candidate startups matching the mandate | `gpt-6-luna` | `web_search`, `fetch_url`, `rss_read` | 300 s | 8 | 0.40 |
| Research Planner | Turn mandate + company into research tasks | `gpt-6-luna` | none | 90 s | 1 | 0.15 |
| Research | Collect sources and extract claims for one task | `gpt-6-luna` | `web_search`, `fetch_url`, `render_page`, `github_read`, filings\_read, `rss_read`, `evidence_lookup` | 240 s | 10 | 0.35 |
| Verification | Grade claims against evidence, find conflicts | `gpt-6-luna` | `evidence_lookup` | 180 s | 3 | 0.30 |
| Evaluation | Score the company against the rubric | `gpt-6-luna` | `evidence_lookup` | 150 s | 1 | 0.25 |
| Critic | Challenge the evaluation independently | `gpt-5.6-terra` | `evidence_lookup` | 180 s | 1 | 0.25 |
| Memo | Write the screening memo | `gpt-6-luna` | `evidence_lookup` | 150 s | 1 | 0.20 |
| Monitoring | Judge materiality of detected changes | `gpt-6-luna` | `fetch_url`, `rss_read`, `github_read`, filings\_read, `diff_snapshots`, `evidence_lookup` | 120 s | 3 | 0.10 |

### 1. Discovery Agent

Runs inside `SourcingBatchWorkflow` on `q.discovery`. Searches permitted sources for companies that pass eligibility filters and returns normalized candidates. Entity resolution then runs deterministically in the Company Identity module, and each accepted candidate is dispatched as an independent screening (see Identity, submission and lifecycle).

```python
class DiscoveryInput(BaseModel):
    mandate: MandateSnapshot           # sectors, stages, geographies, exclusions
    sources: list[SourceSelector]      # e.g. {kind: "rss", feed: "techcrunch-startups"}
    since: datetime
    max_candidates: int = 50

class DiscoveryCandidate(BaseModel):
    name: str
    domain: str | None
    one_liner: str
    sector_guess: str
    stage_guess: Literal["pre_seed", "seed", "series_a", "series_b", "growth", "unknown"]
    hq_country: str | None
    discovered_via: list[EvidenceSpan]  # spans in captured snapshots
    eligibility: dict[str, bool]       # filter_id -> passed
    confidence: float

class DiscoveryOutput(BaseModel):
    candidates: list[DiscoveryCandidate]
    sources_queried: int
    sources_blocked: list[BlockedSource]
```

### 2. Research Planner

Pure reasoning, no tools. Produces a bounded plan; the workflow refuses plans exceeding `max_tasks` or the assessment budget.

```python
class PlannerInput(BaseModel):
    company: CompanyRef
    mandate: MandateSnapshot
    research_questions: list[ResearchQuestion]
    prior_coverage: CoverageReport | None   # set on replanning
    remaining_budget: AgentBudget
    max_tasks: int = 8

class ResearchTask(BaseModel):
    task_id: str                       # "t1"
    question_ids: list[str]
    objective: str
    suggested_sources: list[str]       # source types or domains, never raw instructions
    priority: int                      # 1 = highest
    depends_on: list[str] = []
    est_cost_usd: Decimal

class ResearchPlan(BaseModel):
    plan_id: UUID
    tasks: list[ResearchTask]
    rationale: str
    est_total_cost_usd: Decimal
```

### 3. Research Agent

One execution per `ResearchTask`, run in parallel by `ResearchWorkflow`. Fetching goes through the `SafeFetcher` (SSRF and robots checks); the model sees only normalized text wrapped in `<source>` delimiters.

```python
class ResearchInput(BaseModel):
    company: CompanyRef
    task: ResearchTask
    known_claims: list[ClaimSummary]   # avoid duplicate work

class ResearchOutput(BaseModel):
    task_id: str
    snapshots: list[SourceSnapshotMeta]
    evidence: list[EvidenceSpan]
    claims: list[Claim]                # verification_status = "unverified" at this stage
    unanswered_question_ids: list[str]
    blocked_urls: list[BlockedSource]
```

### 4. Verification Agent

Grades every claim against its passages, detects contradictions across claims, flags stale evidence, and produces the coverage report the workflow uses to decide on gap research.

```python
class VerificationInput(BaseModel):
    company: CompanyRef
    claims: list[Claim]
    research_questions: list[ResearchQuestion]
    freshness_policy: FreshnessPolicy  # max age per subject, e.g. traction: 180 days

class ClaimVerdict(BaseModel):
    claim_id: UUID
    verification_status: VerificationStatus
    support_score: float
    reasoning: str                     # <= 400 chars
    contradicts: list[UUID]

class Contradiction(BaseModel):
    contradiction_id: UUID
    claim_ids: list[UUID]
    description: str
    preferred_claim_id: UUID | None    # by trust tier then recency; None = unresolved

class VerificationOutput(BaseModel):
    verdicts: list[ClaimVerdict]
    contradictions: list[Contradiction]
    coverage: CoverageReport
```

### 5. Evaluation Agent

Scores each rubric criterion with anchored levels. Every score must cite claims; a criterion with no supported claims is scored `null` with `insufficient_evidence = true`, never guessed.

```python
Recommendation = Literal["advance", "hold", "pass", "inconclusive"]   # single vocabulary, see Contracts › Recommendation

class EvaluationInput(BaseModel):
    company: CompanyRef
    mandate: MandateSnapshot
    rubric: Rubric                     # criteria with weight and anchors 1-5
    claims: list[Claim]                # verified only
    findings: list[Finding]            # all kinds, with domain_id
    domains: list[DomainAssessment]    # gate results decide which criteria may be scored
    coverage: CoverageReport
    revision_of: UUID | None
    critique: CritiqueOutput | None    # set on revision

class CriterionScore(BaseModel):
    criterion_id: str                  # "team", "market", "product", "traction", "thesis_fit"
    score: int | None                  # 1-5; None when the criterion's domains are insufficient
    insufficient_evidence: bool
    rationale: str
    supporting_claim_ids: list[UUID]
    counter_claim_ids: list[UUID]
    evidence_strength: Literal["strong", "good", "mixed", "weak"]   # computed from support scores and trust tiers, not chosen by the model

class EvaluationOutput(BaseModel):
    evaluation_id: UUID
    revision: int
    scores: list[CriterionScore]
    measures: Measures                 # four separate measures; attractiveness carries the weighted score
    weighted_score: float | None       # = measures.attractiveness.score (kept for compatibility)
    weighted_score_range: tuple[float, float] | None   # computed deterministically, see below
    advance_threshold: float           # copied from the pinned config for display
    thesis_fit: Literal["strong", "moderate", "weak", "out_of_mandate"]
    uncertainty: Literal["low", "medium", "high"]
    recommendation: Recommendation
    conditions: list[str] = []         # only with "advance": what must be true before a term sheet; each cites finding or risk ids
    key_risks: list[str]
    open_questions: list[str]
```

**Score range and strength are computed, not generated.** After the model returns criterion scores, a deterministic step sets `evidence_strength` per criterion from the support scores and trust tiers of its supporting claims. It then computes `weighted_score_range` by moving each criterion with `mixed` or `weak` strength, or with `insufficient_evidence`, one anchor down and one anchor up (within 1–5) and recomputing the weighted score. `advance_threshold` comes from the pinned configuration's approval rules. The UI draws exactly these numbers.

### 6. Critic Agent

Runs with a different model from the Evaluation Agent (configuration validation rejects the same model ID) and a separate prompt that sees the evaluation but not the evaluator's reasoning trace. The workflow allows at most `max_revisions` (default 2) evaluation revisions.

```python
class CritiqueInput(BaseModel):
    evaluation: EvaluationOutput
    claims: list[Claim]
    rubric: Rubric

class CritiqueIssue(BaseModel):
    criterion_id: str | None
    severity: Literal["blocking", "major", "minor"]
    kind: Literal["unsupported_score", "ignored_counterevidence", "rubric_misapplied", "overconfidence", "bias", "other"]
    description: str
    claim_ids: list[UUID]

class CritiqueOutput(BaseModel):
    critique_id: UUID
    verdict: Literal["accept", "revise", "escalate"]
    issues: list[CritiqueIssue]
    suggested_score_changes: dict[str, int]
```

### 7. Memo Agent

Renders the firm's memo template. Output is structured sections with inline citation markers `[c:<claim_id>]`; a post-processor rejects any sentence containing a number without a marker.

```python
class MemoInput(BaseModel):
    company: CompanyRef
    evaluation: EvaluationOutput
    critique: CritiqueOutput
    claims: list[Claim]
    template: MemoTemplate

class MemoSection(BaseModel):
    key: str                           # "summary", "team", "market", "risks", ...
    title: str
    body_md: str
    cited_claim_ids: list[UUID]

class MemoOutput(BaseModel):
    memo_id: UUID
    assessment_revision: int
    sections: list[MemoSection]
    unverified_statements: int
    word_count: int
    headline: str                      # <= 300 chars, every factual phrase cited; shown as "Our take"
```

### 8. Monitoring Agent

Called by `CompanyMonitoringWorkflow` after a deterministic snapshot diff finds changes. It judges materiality and names the criteria that depend on the changed claims, using stored claim → criterion → memo → decision dependency links. **Amended (P1-08):** monitoring never edits an approved memo or a pinned evidence snapshot. A material change opens a new assessment revision with trigger `monitoring`; the prior revision, memo and decision stay readable and immutable. A source that disappeared is recorded as `source_unavailable`, which is different from evidence that a claim was false.

```python
class MonitoringInput(BaseModel):
    company: CompanyRef
    watch_rules: list[WatchRule]       # e.g. funding, leadership, pricing, hiring_spike; each with cooldown
    diffs: list[SnapshotDiff]          # previous vs current snapshot_id with changed spans
    last_assessment: AssessmentIdentity
    dependency_map_ref: ArtifactRef    # claim -> criterion -> memo section links

class MonitoringEvent(BaseModel):
    event_id: UUID
    dedupe_key: str                    # company + event_type + evidence digest; duplicates are dropped
    event_type: Literal["funding", "leadership_change", "product_launch", "pricing_change", "hiring", "negative_news", "source_unavailable", "other"]
    summary: str
    materiality: Literal["high", "medium", "low", "none"]
    evidence: list[EvidenceSpan]

class MonitoringOutput(BaseModel):
    events: list[MonitoringEvent]
    action: Literal["none", "notify", "new_revision"]
    recompute_criteria: list[str]      # criterion_ids whose claims changed
```

Watch frequency, monthly monitoring spend and notifications per company are capped in configuration; pause and resume are workflow signals that survive restarts.

### Agent extensions for due diligence

The eight roles stay; each gains domain-aware inputs and outputs. Deterministic work (parsing, scanning, financial calculations, gates, reconciliation of numbers) is done by typed components in Activities, not by agents. Typed contracts for these extensions are in the Agent & tool contracts tab.

| Role | Added responsibility | Added inputs | Added outputs |
| --- | --- | --- | --- |
| Discovery | Unchanged; tags candidates with suggested level | — | `suggested_level` |
| Research Planner | Plans per domain from the level, stage, industry and geography profile; plans information requests at Level 3 | `level`, domain profile, gate definitions, document inventory | `DomainPlan[]` (tasks per domain), draft information requests |
| Research | Public research per domain task; at Level 3, extracts claims from private documents through `document_lookup` only (no network in that mode) | Domain task, extraction schema for the domain | Domain claims with public or private spans |
| Verification | Domain verification against the domain's criteria; cross-document reconciliation; cross-domain contradiction analysis; gate inputs | All domain claims, calculation results, reconciliation results | Verdicts, contradictions (intra- and cross-domain), per-domain coverage |
| Evaluation | Domain assessments, risk register, thesis fit, scenarios and key assumptions | Findings, gate results, calculations | `DomainAssessment[]`, `RiskItem[]`, `Scenario[]`, recommendation |
| Critic | Independent risk critique: missed red flags, overstated findings, unsupported numbers, unfair inferences | Evaluation output, findings, risk register | Issues by domain and risk |
| Memo (report generator) | Writes the due diligence report sections for the level from findings only | Report template for the level, findings, risks, calculations | `ReportVersion` (21 sections with status) |
| Monitoring | Also watches new private document versions and information-request responses | Document events | `new_evidence` revisions |

**Why no new agent roles.** Each of the twelve domains is the same pipeline — plan, retrieve, extract, verify, evaluate, critique, report — with domain-specific schemas, criteria and calculations, so the domain is configuration and code, not a new responsibility. Financial analysis is deterministic, so an agent there would add risk without value. A new role would be justified only if a domain needed a decision loop the existing roles cannot express; none does today, and the Change log records that review.

## Workflow wiring

&#91;embedded content: CompanyScreeningWorkflow · 8 agent steps, 2 decisions\]

Gap research and evaluation revisions are the only loops, both capped by iteration count and by budget reservations; the human review gate is a Temporal Update whose validator checks the full `ReviewTarget` (see Human review).

| Workflow | Agents and Activities | Queues | Interaction | Continue-As-New |
| --- | --- | --- | --- | --- |
| `SourcingBatchWorkflow` | Discovery; `resolve_identity`; `start_screening` (idempotent dispatch, no child wait) | `q.discovery` | Schedule or `trigger` signal; max 5 concurrent dispatches | After 500 candidates, carrying a cursor and dedupe digest |
| `CompanyScreeningWorkflow` | Planner, provenance check, Evaluation, Critic, Memo, delivery via outbox | `q.research`, `q.verification`, `q.evaluation`, `q.delivery` | Update `submit_review`; signals `cancel_assessment`, `resume_after_config`; query `progress` | No (bounded) |
| `ResearchWorkflow` (child, parent-close: request cancel) | Fetch, Research ×N, Verification | `q.fetch`, `q.research`, `q.verification` | Query `task_status` | No |
| `ResearchGapWorkflow` (child, parent-close: request cancel) | Planner, Fetch, Research, Verification | same | none | No; max 2 rounds |
| `CompanyMonitoringWorkflow` | Fetch, snapshot diff, Monitoring; starts a new screening revision when material | `q.fetch`, `q.monitoring` | Signals `pause`, `resume`, `update_rules` | Every 50 checks, carrying last snapshot IDs and cooldowns |

Workflow IDs are `dd:{firm_id}:{assessment_id}:r{revision} (see Diligence workflows)`. Duplicate submissions are caught by the API's idempotency and submission-policy rules before any workflow starts, so the workflow ID no longer carries that job (P0-01). Children are used only where cancelling the parent should cancel the research; screenings started by sourcing or monitoring are independent workflows.

## Diligence workflows

The sourcing, screening, research, gap-research and monitoring workflows stay. Level 1 runs on `CompanyScreeningWorkflow`, unchanged in shape. Levels 2 and 3 run on `DueDiligenceWorkflow`, which fans out one child workflow per domain and, at Level 3, waits on document ingestion.

&#91;embedded content: DueDiligenceWorkflow · Level 2 and 3\]

**Workflow identity (modified).** Each assessment revision is its own workflow execution, with ID `dd:{firm_id}:{assessment_id}:r{revision}` for every level. The earlier `screen:{firm_id}:{assessment_id}` is retained only for executions started before this change. Upgrades, new evidence, requests for research and requests for information each start a new revision, so histories stay bounded, replay stays per revision, and an approved revision can never change.

| Workflow | ID | Started by | Work | Run timeout | Cancellation |
| --- | --- | --- | --- | --- | --- |
| `CompanyScreeningWorkflow` (Level 1) | `dd:{firm}:{asm}:r{n}` | Submission at Level 1 | As in Workflow wiring | 2 h, excluding time waiting for review | Request cancel; releases reservations |
| `DueDiligenceWorkflow` (Levels 2–3) | `dd:{firm}:{asm}:r{n}` | Submission at Level 2 or 3, or an upgrade | Plan, domain children, calculations, cross-domain verification, freeze, evaluation, critique, report, review | 24 h, excluding review | Cancels domain children; document ingestion continues |
| `DomainResearchWorkflow` (child, parent-close: request cancel) | `{parent}:d:{domain_id}` | Parent | Research tasks, domain verification, gate check | 4 h | Follows parent |
| `DocumentIngestionWorkflow` | `doc:{firm}:{document_id}:v{version}` | Upload committed | Scan, validate, classify, parse, extract, index; financial validation task when needed | 1 h, plus human validation wait | Independent: documents belong to the deal's data room, not to one revision |
| `ResearchGapWorkflow` (child) | `{parent}:gap:{round}` | Parent after the gate | Bounded follow-up on missing or conflicting evidence | 1 h per round; max 2 rounds per revision | Follows parent |
| `CompanyMonitoringWorkflow` | unchanged | Watchlist | Also reacts to document and information-request events | — | Pause and resume signals |

**Stages and states.** Within `VALIDATING`, a revision passes domain gates, then cross-domain contradiction analysis, then **evidence freeze**: an `EvidenceSnapshotSet` covering every span, calculation and document version used, hashed and pinned to the evaluation, critique, report and review target. Nothing after the freeze can add evidence; new evidence starts a new revision. Review adds the decision `request_information`, which ends the revision in the new state `INFORMATION_REQUESTED` and creates information-request items. When requested documents arrive, a `new_evidence` revision starts automatically if the deal team allows it, or on demand.

**Execution rules.**

- **Retries:** agent Activities follow the agent error taxonomy; tools follow the tool taxonomy. Parsers retry once in a fresh sandbox. Deterministic calculations and gates are not retried except on infrastructure errors.
- **Timeouts:** per agent as in the agent table. Document scan 5 minutes, parse 10 minutes, each per document. Each Activity has a heartbeat timeout of twice its heartbeat interval.
- **Idempotency:** revision workflow IDs; ledger operation IDs per tool and agent call; upload idempotency keys; information-request item IDs.
- **Budgets:** the level budget is reserved at revision start and split into per-domain sub-budgets (configurable weights). Document processing has its own page and size limits, so a large data room cannot starve research. When a domain exhausts its budget it becomes `inconclusive`; it does not stop other domains.
- **Parallelism:** at most 4 domain children per revision by default, within the tenant's concurrency limit.
- **Partial failure:** a failed domain child records its failure and gate result `inconclusive`; the parent continues and the report marks the section incomplete. Retrying one domain starts only that child in a new revision.

## Human review

A decision applies only to the exact versions the reviewer saw: assessment revision, evidence snapshot, evaluation, memo and review policy (P1-01). Matching the revision number alone is not enough.

```python
class ReviewTarget(BaseModel):
    assessment_id: UUID
    assessment_revision: int
    evidence_snapshot_id: UUID         # the frozen EvidenceSnapshotSet
    evaluation_id: UUID
    memo_version_id: UUID              # holds the report_version_id (compatibility name)
    review_policy_version: str         # "single-reviewer@1"
    # target_digest = sha256 of the canonical JSON above; returned by GET and echoed on submit

class SubmitReviewRequest(BaseModel):
    target: ReviewTarget
    decision: Literal["approve", "reject", "request_research", "request_information"]
    comment: str | None = None
    requested_items: list[str] = []    # required and non-empty when decision == "request_information"
    idempotency_key: str
```

**Flow.** The API resolves tenant and reviewer from the session, checks the reviewer's role against the policy, and compares the full target with the authoritative database record. It then writes a `review_pending` row and sends the Temporal Update `submit_review`. The Update validator re-checks the target against workflow state, the handler records the decision, and the API marks the row accepted. If the Update fails after the row was written, a reconciler resolves it from workflow history; the row never claims acceptance on its own.

| Case | Response |
| --- | --- |
| Target matches, reviewer authorized | `200` with decision record and audit event ID |
| Any target field outdated | `409 STALE_REVIEW_TARGET` with the current target |
| Reviewer lacks the required role, or role revoked | `403 REVIEW_NOT_AUTHORIZED` |
| Same idempotency key retried | `200` with the original accepted result |
| Decision already recorded by another reviewer | `409 REVIEW_ALREADY_DECIDED` with the winning decision |
| Review expired under policy | `409 REVIEW_EXPIRED`; escalation task created |

**Default policy: one authorized reviewer decides** (`single-reviewer@1`); the first accepted Update wins and the workflow serializes concurrent Updates, so two simultaneous decisions cannot both apply. A `quorum@1` policy (N of M approvals, any reject wins) is available through configuration. Pending reviews expire after 7 days by default and escalate to the firm's admins.

**Who may decide.** The pinned configuration's approval rules set `advance_threshold` (default 3.5). Analysts may decide when the weighted score is below it; at or above it a partner, admin or owner must decide. The rule is checked on the server against the target's evaluation, and the queue shows each reviewer only what they may decide.

**Feedback capture.** On any memo, a reader can mark it useful or not, pick reasons (missed a key fact, wrong fact, weak sources, unclear, other) and point at a claim or section. `POST /assessments/{id}/feedback { memo_version_id, rating, reasons[], claim_ids[], comment }` stores a `Feedback` row (firm, assessment, memo version, user, rating, reasons, claims, comment) and emits `feedback.recorded` to the console. Feedback feeds the quality harness as candidate labels after review. It is never used to tune the system toward past investment decisions.

When new critical evidence arrives during review, the workflow supersedes the pending target, creates a new revision and returns the assessment to evaluation. Late decisions against the old target get `409 STALE_REVIEW_TARGET`. `request_research` reopens public research as a new revision. `request_information` (deal team, Level 3, or any level as a note) ends the revision in `INFORMATION_REQUESTED`, turns each `requested_items` entry into an `InformationRequest` in status `draft`, and emits `information_request.updated`. Finalized decisions are never edited.

## Failure handling and consistency

**Credentials and outages (P1-04).** A missing, invalid or quota-limited key is a setup condition, not an outage. The API validates provider configuration before accepting live work and rejects live submissions with `422 PROVIDER_NOT_CONFIGURED` and a fix-it message. An in-flight assessment that hits `CREDENTIALS_*` or `PROVIDER_QUOTA_EXCEEDED` stops its Activity, moves to `BLOCKED_CONFIGURATION` and waits on the `resume_after_config` signal, which the UI sends from a Resume button once `/system/status` reports the provider healthy again. 429 and 5xx responses use bounded backoff inside the Activity; Temporal retry policy is a ceiling, not the place where retry hints are parsed. Partial results are persisted and the assessment shows `degraded` until it recovers. There is no demo binding: the demo workspace runs on the same workers, and any step that needs a model stops with `PROVIDER_NOT_CONFIGURED` until a key is set.

**Who owns what (P1-05).**

| State | Authoritative store | Others hold |
| --- | --- | --- |
| Process progress, timers, pending reviews | Temporal | Read-model projection in PostgreSQL |
| Assessments, claims, reviews, audit, ledger, outbox | PostgreSQL | References in workflow state |
| Raw and normalized captures, memos, prompts | Object storage | IDs and hashes in PostgreSQL |

A reconciler runs every 10 minutes and on demand. It finds workflows that completed without database finalization, assessment rows with no live workflow, artifact references whose object is missing or whose hash differs, outbox events stuck past their retry window, expired budget reservations, and ledger rows left `UNKNOWN`. Each repair is an idempotent, audited action; running the reconciler twice changes nothing the second time. Repair actions through the API need the `admin` role.

**Temporal evolution (P1-06).** Temporal server and Python SDK versions are pinned in docker-compose.yml and pyproject.toml, with tested combinations recorded in `docs/compatibility.md`. Workflow code changes use the SDK's `workflow.patched()` markers or Worker Versioning build IDs, so histories recorded before a deploy keep replaying. CI replays a stored corpus of real histories, including one paused in review, against every workflow change and fails on non-determinism. Configuration, prompts, model IDs, evidence and workflow code are versioned separately and each pinned on the assessment. Continue-As-New carries only compact state: cursors, last snapshot IDs, cooldowns and counters. Cancellation runs cleanup Activities to release reservations and close the ledger; termination is reserved for operators and leaves the reconciler to tidy up.

**Replay from ledger (operator tool).** "Replay from ledger" re-executes an existing run deterministically for debugging: a new assessment with trigger `reassessment` and flag `ledger_replay` runs on the `q.replay` worker, whose `ReplayProvider` serves the provider responses recorded in the original run's ledger artifacts. Search, fetch and storage are real. No model provider is called and no money is spent. If any original response is missing, the API returns `409 REPLAY_UNAVAILABLE`. Replays are visible in the console only, are labelled "replay", never appear in the Diligence app, and never count toward acceptance. `worker-replay` is started only with `--profile ops`.

**Observability.** OpenTelemetry traces span API request → workflow → Activity → provider call, carrying `firm_id`, `assessment_id` and `operation_id` as attributes; prompts and responses are never attached. Metrics cover queue backlog and pollers, Activity latency and retries, provider errors by code, spend by certainty, reservation failures, event-stream connections and SSE lag. Logs are structured JSON with redaction. The local `observability` Compose profile adds a collector, Prometheus, Grafana and Tempo with prebuilt dashboards, and the console's run detail links to the trace of each operation.

**Provider failures and coverage.** Tool failures never fail the whole workflow. Each failed or degraded call is recorded as a `SourceGap` on the coverage report, naming the tool, error code and the research questions it affected. Unaffected tasks finish. The Evaluation Agent raises `uncertainty` when must-questions have source gaps, and the memo gets a "Coverage limits" line naming them, such as "Web search was degraded during this review; news coverage may be incomplete." An empty search result is recorded as "no results returned", never as "no online presence".

## API contracts consumed by the UI

All routes are under `/api/v1`, require a bearer session, and resolve `firm_id` from the session membership — never from the request body. List endpoints return `{ items, next_cursor, total }`. Errors return `{ error: { code, message, details, request_id } }`.

| Method & path | Returns | Used by page |
| --- | --- | --- |
| `GET /health/ready` | dependency checks: Postgres, migrations at head, MinIO, Temporal, pollers per queue | Compose health check |
| `GET /system/status` | `{ mode: "setup_required" \| "demo_ready" \| "live_ready" \| "degraded", provider: { state, models: [{ role, model_id, available }] }, queues: [{ name, pollers, backlog }] }` | Global status bar |
| `GET /dashboard/summary` | counts by lifecycle state, spend today with certainty split, approvals pending, recent events | Dashboard |
| `POST /companies` | body `{ name, domain?, policy }`, header `Idempotency-Key` → `SubmitCompanyResponse`; `409 IDEMPOTENCY_KEY_CONFLICT`; `422 PROVIDER_NOT_CONFIGURED` in setup mode | Submit company |
| `GET /companies?q=&state=` | `CompanyListItem[]` with latest assessment and identity confidence | Company directory |
| `GET /assessments/{id}` | `AssessmentDetail`: identity, lifecycle state, revision history, four scores, budget | Assessment detail |
| `GET /assessments/{id}/workflow` | stages with status, attempts, queue and error | Workflow tab |
| `GET /assessments/{id}/claims` | `Claim[]` with spans, provenance result and verdict | Evidence tab |
| `GET /evidence/{evidence_id}/citation` | URL, capture date, excerpt allowed by access policy (authorized per tenant) | Citation popover |
| `GET /assessments/{id}/evaluation` | `EvaluationOutput` + `CritiqueOutput[]` with pinned snapshot | Evaluation tab |
| `GET /assessments/{id}/memo` | `MemoOutput` with `memo_version_id` | Memo tab |
| `GET /assessments/{id}/operations` | ledger rows: operation, queue, status, attempts, cost and certainty | Agent runs tab |
| `GET /reviews?status=pending` | `ReviewQueueItem[]` with current `ReviewTarget` and digest | Approvals |
| `POST /assessments/{id}/review` | `SubmitReviewRequest`; see Human review for responses | Approval action |
| `POST /assessments/{id}/resume` | resumes `BLOCKED_CONFIGURATION` once the provider is healthy | Resume button |
| `GET /watchlist`, `POST /watchlist`, `PATCH /watchlist/{id}` | entries with rules, cadence, caps, paused flag | Watchlist |
| `GET /monitoring/events` | `MonitoringEvent[]` with action taken | Monitoring feed |
| `GET /config/current`, `POST /config/versions` | validated `ConfigVersion` with diff; never alters pinned assessments | Configuration |
| `GET /usage?from=&to=` | cost and tokens per role and day, split by `cost_certainty` | Usage |
| `GET /ops/reconciliation`, `POST /ops/reconciliation/run` | last run, findings, repairs (admin) | Operations |
| `POST /tenant/export`, `POST /tenant/delete-requests`, GET /tenant/delete-requests | export bundle or deletion job ID (owner) | Settings |

The frontend types in `web/lib/types.ts` are generated from the OpenAPI schema in CI, and a check fails the build if they drift. Every error carries a stable `code` so the UI can show a specific next step rather than a generic failure.

**Summary views.** Investor pages request `?view=summary`. The server returns a separate response model that omits operation IDs, queues, token counts, attempts, digests and raw error codes; this is enforced by the response model, not by the UI.

```python
class AssessmentSummaryView(BaseModel):
    assessment_id: UUID
    company: CompanyRef
    revision: int
    level: Literal[1, 2, 3]
    state: AssessmentState
    stage: Stage | None                # finer step inside the state, see Progress and stages
    status_copy_key: str               # key into the status-copy table
    recommendation: Recommendation | None
    conditions: list[str] = []
    headline: str | None               # report section 1, first paragraph
    measures: Measures | None          # source_reliability, claim_confidence, evidence_coverage, attractiveness — never combined
    domains: list[DomainStatusSummary] # 12 rows: domain_id, status, gate_result, reason, found, required, counts
    finding_counts: dict[FindingKind, int]   # the seven finding kinds
    open_risks: int
    open_requests: int                 # 0 for viewers outside the deal team when all requests are private
    advance_threshold: float
    thesis_fit: Literal["strong", "moderate", "weak", "out_of_mandate"] | None
    scorecard: list[ScorecardRow]      # attractiveness breakdown only; never shown as an overall score
    progress: Progress | None          # domains_complete, domains_total while active
    can_decide: bool                   # computed for the caller from role, deal team and advance_threshold
    report_version_id: UUID | None
    # Removed in this version (still returned under ?compat=research until the next major API version):
    # weighted_score, weighted_score_range, uncertainty, evidence_counts, questions, research_summary
```

Fields restricted to the deal team (private finding counts by domain, private risks and requests) are filtered on the server for other viewers; counts are recomputed from what they may see, so totals never reveal hidden items.

**Error codes.** Every error body is `{ error: { code, message, details, request_id } }`. Codes are stable and listed in `schemas/errors.json`, which the frontend imports for its copy table.

| HTTP | Codes |
| --- | --- |
| 400 | `VALIDATION_FAILED` |
| 401 | `UNAUTHENTICATED` |
| 403 | `FORBIDDEN`, `REVIEW_NOT_AUTHORIZED` |
| 404 | `NOT_FOUND`, `MEMO_NOT_READY` |
| 409 | `IDEMPOTENCY_KEY_CONFLICT`, `STALE_REVIEW_TARGET`, `REVIEW_ALREADY_DECIDED`, `REVIEW_EXPIRED`, `RESOLUTION_EXPIRED`, `ALREADY_WATCHING`, `CONFIG_BASE_OUTDATED`, `PROVIDER_NOT_READY`, `REPLAY_UNAVAILABLE`, `ALREADY_TERMINAL`, `RECONCILIATION_RUNNING` |
| 413 | `PAYLOAD_TOO_LARGE` |
| 422 | `PROVIDER_NOT_CONFIGURED`, `CONFIG_INVALID`, `OVER_TENANT_CAP` |
| 429 | `RATE_LIMITED` (with `Retry-After`) |
| 503 | `DEPENDENCY_UNAVAILABLE` (readiness failing) |

## Two interfaces: investor app and agent console

The web UI is split by audience. Investors get an app about companies, evidence and decisions in plain language; operators get a console about agents, workflows, costs and recovery. Both are route groups in one Next.js service (`/` and `/console`), so Docker Compose and the first-run experience are unchanged.

|  | Investor app (`/`) | Agent console (`/console`) |
| --- | --- | --- |
| Audience | Partners, analysts | Operators, firm admins, maintainers |
| Role required | `analyst`, `partner` | `operator`, `admin` |
| Pages | Home, Companies, Company and assessment, Decisions, Watchlist, Thesis | Runs, Run detail, Health, Costs and budgets, Reconciliation and outbox, Sourcing, Quality, Configuration (models, budgets, sources, review policy), Audit log, Data and retention (owner) |
| Shows | Memo, scores, citations, contradictions, uncertainty, progress as questions answered, decisions | Workflow stages, queues, pollers, operation ledger, cost certainty, reservations, provenance failures, quarantined sources, replay status |
| Never shows | Queue names, operation IDs, tokens, retries, digests, raw error codes | Private memo text beyond what an action needs |
| Actions | Submit, choose submission policy, approve, reject, request research, watch | Resume, cancel, rerun, reconcile, switch to fixtures, export run trace |
| Endpoints | `/companies`, `/assessments/{id}` (summary views), `/reviews`, `/watchlist`, `/config/current` (thesis and rubric only) | `/system/status`, `/assessments/{id}/workflow`, `/assessments/{id}/operations`, `/usage`, `/ops/*`, `/config/current` (models, budgets, sources) |

**Status translation.** The investor app maps system states to plain sentences through one shared table in `web/lib/status-copy.ts`, so wording is consistent and testable.

| System state | Investor app says |
| --- | --- |
| `CREATED` | Starting research |
| `PLANNING`, `RESEARCHING`, `VALIDATING` | Researching · 9 of 14 key questions answered |
| `EVALUATING`, `CRITIQUING`, `MEMO_READY` | Writing the memo |
| `AWAITING_REVIEW` | Ready for your decision (or "Waiting for a partner" when the caller cannot decide) |
| `RESEARCH_REQUESTED` | More research requested · a new version is on its way |
| `APPROVED`, `DELIVERING` | Advanced · sharing with your tools |
| `REJECTED` | Passed |
| `COMPLETED` | Advanced, Watching or Passed, with the decision date |
| `WATCHLISTED` | Watching |
| `ARCHIVED` | Archived |
| `BLOCKED_CONFIGURATION` | Paused: live research needs setup. Your admin has been notified. |
| `BUDGET_EXHAUSTED` | Stopped at its spending limit. Partial findings are available. |
| `CANCELLED` | Stopped by an admin |
| `FAILED` | Something went wrong. Your admin has the details. |
| `degraded` mode | Research is running slower than usual. |
| `409 STALE_REVIEW_TARGET` | This memo changed while you were reading it. Review the new version. |
| `409 REVIEW_ALREADY_DECIDED` | Marco Lee decided this a moment ago. |
| `403 REVIEW_NOT_AUTHORIZED` | Your role can't decide this one; a partner needs to. |

**Claim labels.** Each claim shows one label, chosen in this order; the evidence bar groups them as shown.

| Condition | Label | Evidence-bar group |
| --- | --- | --- |
| `provenance_valid = false` | Could not be checked | unverified |
| `contradicted` | Sources disagree | disagree |
| `supported` | Confirmed | confirmed |
| `partially_supported` | Partly confirmed | partial |
| `outdated` | Out of date | partial |
| `source_unavailable` | Source no longer online | unverified |
| `not_publicly_verifiable` | Not public | unverified |
| `unverified` | Not confirmed | unverified |

**Links between them.** Every investor-facing problem notice carries a "View in agent console" link shown only to users with console access; it opens the exact run. Every console run links back to its company page. Investors are never left with a silent failure: anything blocked, degraded or stopped is stated in one sentence with what happens next.

The Temporal Web UI (port 8233) and the optional Grafana profile remain available for deep workflow history and metrics; the console covers what those tools do not, namely ledger, budgets, provenance, quality and reconciliation. Gate F tests the two journeys separately: investor submit → progress → memo → decision, and operator blocked run → fix → resume → reconcile. A role test checks that analysts get 403 on every console route.

## Private documents

At Level 3, authorized users add private materials to the assessment's **data room**. Private evidence is never searched outside the workspace, never sent to a web tool, never used for another assessment, firm or company, and never shown to anyone outside the deal team.

**Supported formats and parsers.** Anything else is rejected at upload with a clear reason.

| Format | Parser | Extracts | Not supported |
| --- | --- | --- | --- |
| PDF | pypdf (text), pdfplumber (tables; MIT, built on pdfminer) | Page text, tables with page and bounding box | Encrypted or password-protected files. Scanned or garbled pages go to local Tesseract OCR automatically (D4). |
| DOCX | python-docx (MIT; confirmed by the D5 licence gate at pin) | Paragraphs, headings, tables | Legacy `.doc` |
| PPTX (pitch decks) | python-pptx (MIT) | Slide text, tables, speaker notes, slide numbers | Legacy `.ppt` |
| XLSX | openpyxl (MIT) in read-only mode with defusedxml installed, as its documentation advises | Cell values, cached formula results, formulas as text, sheet and range | `.xls`, `.xlsm` and other macro-enabled files; formulas are never evaluated |
| CSV | Python `csv` with delimiter and encoding detection | Rows and headers | Files over the row limit |

**Ingestion pipeline** (`DocumentIngestionWorkflow`):

1. **Authorize:** the uploader is on the deal team and Level 3 is enabled for the assessment. (Upload never depends on external AI consent; D1 governs only model calls.)
2. **Limits:** 50 MB per file, 1 GB per data room, 2,000 pages per PDF, 100 sheets or 1 million cells per workbook (configurable).
3. **Store:** the file is encrypted and written to a quarantine bucket.
4. **Validate:** the type is sniffed with libmagic and must match the extension. OOXML packages are inspected for entry count, compression ratio, macros, ActiveX, embedded OLE objects and external links; any of these rejects or flags the file. PDF JavaScript and launch actions are flagged (parsers never execute them).
5. **Scan:** ClamAV (`clamd`) is reached over a Unix socket on the internal network. The official `clamav/clamav` image ships with signatures preloaded, so the demo seed's documents are scanned even without internet; `freshclam` updates signatures when internet is available. An infected file is quarantined, audited and reported to the uploader; a scan error holds the file.
6. **Parse:** in `worker-docs`, a sandbox with no network, a read-only root, a non-root user, the default seccomp profile, a 2 GB memory limit, 120 seconds of CPU per document, one document per process, and temporary files wiped afterwards.
7. **Classify:** rules plus the LLM sort the file into pitch deck, financial statements, forecast, KPI export, cap table, financing document, customer or pipeline list, commercial contract, security document, IP document, regulatory or legal document, or other. The uploader confirms or corrects the class.
8. **Extract:** structured extraction runs per class (schemas in the Domain specification tab), followed by validation (financial data goes through Financial analysis).
9. **Index:** normalized text with offsets is indexed in full-text search, encrypted at rest. It is embedded only if the workspace allows provider processing.

**Private citations.** Every private span records `document_id`, `version`, file `sha256`, extractor version, location (page, slide, `Sheet!A1:D20`, or paragraph index) and character offsets into the stored normalized text. They are checked exactly like public spans.

**Encryption and retention.** Envelope encryption: each data room has a data key (AES-256-GCM) wrapped by a master key from `DOCS_MASTER_KEY` or a configured KMS. Originals, normalized text and sensitive excerpt fields are encrypted before they reach MinIO or PostgreSQL. Versions are immutable; re-uploading creates a new version, and findings pin versions. Deleting a version or the data room deletes its objects and destroys its data key, which makes backups unreadable. Approved reports keep citation metadata but show "document deleted". Retention follows D2: deletion 90 days after the assessment closes (admins may only shorten), with legal holds, immediate deletion and verified Temporal cleanup.

**Access.** Each assessment has a deal team: the owner, admins, and named analysts and partners. Only deal-team members can open private documents, private findings and Level 3 reports. Console operators see document metadata (type, size, status, errors) but never content.

**Model processing (decided, D1).** Private material never goes to an external AI provider by default. Model calls on private data use a verified local model, or OpenAI only when a workspace owner or admin has authorized the specific data categories and purposes; otherwise the step is skipped and reported. Enforcement is in `PolicyEnforcedProvider` before every request. See Approved decisions › D1.

**Private evidence stays local.** An agent invocation whose context includes private evidence gets no network tools for its lifetime, and the Tool Registry rejects any `web_search`, `fetch_url`, `render_page`, `github_read` or `filings_read` request from it. This stops private facts from leaking into search queries.

**Instructions inside documents.** Document text enters prompts only as data. Text that tries to instruct the AI is recorded as a finding ("document contains instructions addressed to an AI system"), because that can itself be material.

## Financial analysis

Every number in a report comes from either a cited source span or a calculation result, and calculations run only in `ddcalc`, a deterministic Python module using `Decimal`. Models never compute, round or estimate figures. The report post-processor rejects any figure without a span or `calculation_id`.

**Normalization.** Extracted tables are mapped to canonical line items. These cover revenue, cost of revenue and gross profit; operating expenses split into sales and marketing, R&D and G\&A; operating income and cash; operating, investing and financing cash flows; headcount; customer counts; MRR movements (new, expansion, contraction, churn); and cohort tables.

Each `FinancialTable` records periods, currency, unit scale, basis (actual, forecast or budget), accounting basis (GAAP, IFRS, management accounts or cash) and the source cell of every value. Rules propose the mapping first and the LLM proposes any remaining items, each with a confidence score.

**Validation and human correction.** Spreadsheets are not assumed to be interpretable automatically. Validators check:

- subtotals and totals (0.5% tolerance);
- the balance-sheet identity;
- cash continuity between periods;
- period gaps and overlaps;
- consistent currency and units;
- sign conventions and duplicate rows;
- forecast mislabelled as actual;
- ARR against MRR × 12.

Low-confidence mappings and failed rules go to the **financial validation queue**, where a deal-team member confirms or corrects each mapping and value. Corrections are audited and produce a new validated version. Calculations run on validated tables only. Figures from unvalidated tables may appear as `source_supported` with an "unvalidated" label, never as `verified_fact`.

**Formulas** (version `ddcalc@1`). A metric whose inputs are missing returns `not_computable` with the list of missing inputs; nothing is filled in.

| Metric | Formula | Required inputs | Unit and period | Rules and assumptions |
| --- | --- | --- | --- | --- |
| Revenue growth | (Revenue\_t − Revenue\_t−1) / Revenue\_t−1; CAGR = (end / start)^(1/years) − 1 | Revenue by period, same basis | % per period | Same currency and basis; no mixing of actual and forecast |
| Gross margin | (Revenue − Cost of revenue) / Revenue | Revenue, cost of revenue | % per period | Cost-of-revenue definition recorded from source |
| Gross burn | Total cash operating expenses | Cash opex by month | Currency per month | Cash basis preferred; accrual flagged |
| Net burn | Cash\_start − Cash\_end, excluding financing inflows | Cash balances, financing flows | Currency per month | Trailing 3-month average reported alongside |
| Runway | Cash\_latest / average net burn (trailing 3 months) | Latest cash, 3 months of net burn | Months | Not computed when net burn ≤ 0; stated as "cash-flow positive in period" |
| MRR and ARR reconciliation | ARR\_reported vs MRR\_latest × 12 vs sum of active contract values | Any two of the three | Currency | Difference over 5% becomes a contradiction finding |
| Net revenue retention | (MRR\_start + expansion − contraction − churn) / MRR\_start, for the cohort active at start | Cohort MRR movements over 12 months | % | Excludes new customers; cohort window stated |
| Gross revenue retention | (MRR\_start − contraction − churn) / MRR\_start | Same | %, capped at 100% | — |
| Customer acquisition cost | Sales and marketing spend / new customers in period | S&M spend, new customer count | Currency per customer | Optional one-period lag recorded as an assumption |
| Lifetime value | ARPA × gross margin / monthly customer churn rate | ARPA, gross margin, churn | Currency | Not computed when churn data covers under 6 months |
| CAC payback | CAC / (ARPA × gross margin) | CAC, ARPA, gross margin | Months | — |
| Customer concentration | Share of revenue from top 1, 5 and 10 customers; HHI = Σ share² | Revenue by customer | % and index | Requires customer-level revenue; anonymized IDs acceptable |
| Forecast vs actual | (Actual − Forecast) / Forecast per line and period | Matched forecast and actual tables | % | Forecast version and date recorded |
| Ownership and dilution | Fully diluted ownership = holder shares / fully diluted shares. Scenario: new shares = investment / price per share, with price per share = pre-money / pre-round fully diluted shares (pool top-up before or after the round as configured); SAFEs and notes convert at the lower of cap price and discounted price | Cap table, round terms, instrument terms | % and shares | Conversion assumptions listed per instrument; scenarios never presented as facts |

```python
class CalculationResult(BaseModel):
    calculation_id: UUID
    metric: str                        # "net_revenue_retention"
    formula_version: str               # "ddcalc@1"
    status: Literal["computed", "not_computable", "flagged"]
    value: Decimal | None
    unit: str                          # "percent", "months", "USD"
    currency: str | None
    period: PeriodRange
    inputs: list[InputRef]             # financial_table_id, version, cell or span, value
    assumptions: list[str]
    missing_inputs: list[str] = []
    validation_issues: list[str] = []
```

Every formula has property-based tests (for example: retention is unchanged when no movements occur, and growth of a constant series is zero) plus golden fixtures, and the module has no I/O.

## Legal, commercial and security review

These reviews run as structured checklists inside domains 8, 9, 10 and 6. Each item produces one of three outputs: an **issue** (evidence of a problem), an **inconsistency** (sources disagree), or a **follow-up question** (evidence missing or unclear), each with citations. The system never states legal conclusions ("the company owns its IP"), audit opinions or security certifications. Every report section in these areas carries the notice: "Automated review to support diligence; not legal, accounting or security advice."

| Area | Checklist items | Level 2 evidence (public) | Level 3 evidence (private) |
| --- | --- | --- | --- |
| Corporate structure | Legal entity, jurisdiction, subsidiaries, registered officers, name history | Company registries, EDGAR, company site | Certificate of incorporation, org chart, entity list |
| Equity and financing rights | Share classes, preferences, pro-rata, board seats, protective provisions, outstanding SAFEs or notes | Form D and similar filings, funding announcements | Cap table, charter, SPA, SAFE and note terms, side letters |
| IP ownership and assignments | Founder and employee invention assignment, contractor IP terms, patents and trademarks, open-source licence exposure | Patent and trademark records where an adapter exists, public repositories' licences | IP assignment agreements, patent filings, OSS inventory |
| Material contracts | Top customer and supplier agreements, exclusivity, change of control, termination for convenience, MFN, liability caps | Press releases, public procurement awards | Commercial agreements, MSAs, order forms |
| Litigation and regulatory | Active or past lawsuits, regulatory actions, licences required for the activity, sanctions exposure | Court records where an adapter exists, regulator notices, news | Litigation summary, regulatory correspondence, licences |
| Customer concentration and obligations | Revenue share by top customers, contractual commitments, SLAs and penalties | Public customer logos and case studies (company-controlled) | Customer revenue table, contracts, SLA terms |
| Data protection and privacy | Personal data categories, lawful basis, DPAs, data residency, subprocessors, breach notifications | Privacy policy, subprocessor list, public breach reports | DPAs, records of processing, DPIAs, breach log |
| Security controls and incidents | Certifications claimed, pen-test cadence, incident history, access control, vulnerability management | Trust page, security.txt, public incident disclosures | SOC 2 or ISO reports, pen-test summaries, policies, incident reports |
| Vendor and infrastructure dependencies | Cloud and model providers, single points of failure, critical vendors | Status pages, documentation, job posts | Architecture documents, vendor list, BCP and DR plans |

**Rules.** A missing document produces a follow-up question and an information request, never an assumption that the document does not exist. A claim from the company's own materials is `source_supported` until corroborated by a third-party or primary record. Certification claims (for example SOC 2) are marked verified only when the report itself or the issuer's public registry confirms them.

## Due diligence report

The Memo Agent writes one report per revision from findings, risks and calculations only. Each section carries a status:

- `supported`: the gate passed;
- `incomplete`: the gate is partial or inconclusive, and the section says what is missing;
- `not_applicable`: for example, regulatory exposure for an unregulated product, with the reason;
- `unavailable_at_level`: the level cannot produce it, with the upgrade that would.

The report schema is in the Agent & tool contracts tab.

| # | Section | Main domains | L1 | L2 | L3 |
| --- | --- | --- | --- | --- | --- |
| 1 | Executive investment summary | All | Yes | Yes | Yes |
| 2 | Company overview | 1 | Yes | Yes | Yes |
| 3 | Investment-thesis alignment | 12 | Yes | Yes | Yes |
| 4 | Business model | 1 | Yes | Yes | Yes |
| 5 | Founder and team assessment | 2 | Yes | Yes | Yes |
| 6 | Market opportunity | 3 | Yes | Yes | Yes |
| 7 | Competitive landscape | 4 | Yes | Yes | Yes |
| 8 | Product and technology | 5 | Yes | Yes | Yes |
| 9 | Traction and commercial performance | 6 | Public signals | Public | Public + private |
| 10 | Financial analysis | 7 | Unavailable | Public figures only | Calculated from validated data |
| 11 | Fundraising and capitalization | 8 | Announcements | Filings + announcements | Cap table and terms |
| 12 | Legal and regulatory risks | 9 | Unavailable | Public records | Public + private |
| 13 | Security and operational risks | 10 | Unavailable | Public signals | Public + private |
| 14 | Material red flags | All | Yes | Yes | Yes |
| 15 | Contradictory or disputed findings | All | Yes | Yes | Yes |
| 16 | Evidence coverage and confidence | All | Yes | Yes | Yes |
| 17 | Missing information and requested documents | All | Yes | Yes | Yes, with request status |
| 18 | Investment scenarios and key assumptions | 7, 8, 12 | Unavailable | Qualitative | Quantified with `ddcalc` |
| 19 | Recommended next diligence actions | All | Yes | Yes | Yes |
| 20 | Investment committee considerations | 11, 12 | Unavailable | Yes | Yes |
| 21 | Evidence appendix and audit trail | All | Yes | Yes | Yes |

**Useful without a recommendation.** When the recommendation is `inconclusive`, the report still delivers sections 14–17 and 19 in full. In that case the executive summary leads with what is known, what is missing, and the cheapest next step.

**Versions and formats.** A `ReportVersion` is immutable once its revision is approved; new evidence creates a new revision and report version, and the UI shows the differences. Formats:

- **Web:** in the Research app.
- **PDF:** printed by Chromium from the internal report HTML on `worker-browser`, with network disabled for that render. Playwright documents PDF generation as Chromium-only.
- **DOCX:** python-docx.
- **JSON:** the report schema.

Every export carries the level, revision, evidence snapshot hash, approval status and the not-advice notice. Exports of Level 3 reports are watermarked with the requester and time, and can be downloaded by deal-team members only.

## Real-time events and UI endpoints

The backend owns the event catalog that both UIs consume; the full contract, including payload fields and client rules, is mirrored in [Thesis UI — Implementation Prompt for the Coding Agent](https://claude.ai/artifact/6WN8xbxht3tUoCurYXiavU), and CI keeps the two identical.

- **Source of truth:** one JSON Schema per event type in `schemas/events/`, with example payloads in `schemas/events/examples/`, served at `GET /api/v1/events/schema`. Adding or changing an event means a new schema file and a version bump; the previous version is kept for one release.
- **Emission:** events are written to the outbox in the same transaction as the change they describe. A dispatcher assigns a ULID `id` and a per-subject `sequence`, stores them in an `events` table kept 72 hours, and publishes them.
- **Delivery:** `GET /api/v1/events/stream?audience=research|console` (SSE). The gateway applies the caller's `TenantContext` and role; console events never reach analysts. It sends heartbeats every 15 s, supports `Last-Event-ID` replay, and sends `resync` when the gap is older than retention.
- **Envelope:** `{ id, type, version, occurred_at, sequence, subject { kind, id }, audience, data }`.
- **Research events:** `assessment.created`, `assessment.state_changed`, `assessment.progress`, `assessment.revision_created`, `assessment.memo_ready`, `review.requested`, `review.decided`, `review.superseded`, `monitoring.event_detected`, `watchlist.updated`, `config.version_created`, `notification.created`, `system.status_changed` (mode only).
- **Console events:** `run.state_changed`, `run.stage_started`, `run.stage_completed`, `operation.updated`, `budget.reservation_changed`, `budget.exhausted`, `budget.override_applied`, `finding.recorded`, `queue.health_changed`, `reconciliation.completed`, `outbox.delivery_changed`, `export.ready`, `quality.report_published`, `config.version_created`, `system.status_changed` (full).
  - **Added console events:** `sourcing.batch_completed` (`batch_id, candidates, eligible, duplicates_merged, dispatched`) and `feedback.recorded` (`feedback_id, assessment_id, memo_version_id, rating, reasons[]`).
- **Tests:** a backend test asserts each emitted event validates against its schema and that every catalog type has an example. The frontend parses the same examples, so a type present on one side only fails both pipelines.

**Endpoints added for the UI** (beyond the API table above)

| Method & path | Purpose |
| --- | --- |
| `GET /me`, `PATCH /me/preferences`, `POST /me/workspace` | Session identity and roles, theme preference, switch to the read-only sample workspace |
| `GET /companies/{id}`, `GET /assessments?state=&view=summary` | Company header; active and recent assessments for Home |
| `POST /identity-resolutions/{request_id}` | Resolve an ambiguous company match from submission |
| `GET /reviews/{assessment_id}` | Current `ReviewTarget` for one assessment |
| `GET /assessments/{id}/questions`, `/revisions`, `/timeline`, `/budget`, `/findings`, `/memo.pdf` | Key-questions matrix, version history, Gantt spans, reservation hierarchy, findings, memo export |
| `POST /assessments/{id}/cancel`, `/budget-overrides`, `/trace-exports`, `/fixture-runs` | Console run actions |
| `POST /operations/{id}/acknowledge` | Clear a possible-duplicate notice |
| `GET /ops/runs`, `/ops/attention`, `/ops/outbox/summary`, `/ops/quality/latest`, `/ops/versions`, `/ops/audit?subject=&actor=&cursor=`, `GET /budgets` | Console lists, summaries and the audit log |
| `GET /config/current?scope=thesis\|agents\|budgets\|sources\|review`\|retention, `POST /config/versions` | Read and save configuration by scope; roles per the matrix above |
| `GET /notifications`, `POST /notifications/{id}/read` | Notifications popover |
| `GET /events/stream`, `GET /events/schema`, `POST /client-errors` | Real-time delivery, schema bundle, client-side contract violations |
| `GET /tenant/members`, `PATCH /tenant/members/{id}` | Membership and roles (owner) |

| Method & path | Purpose |
| --- | --- |
| `GET /ops/sourcing/batches`, `GET /ops/sourcing/batches/{id}`, `POST /ops/sourcing/batches` | Sourcing runs: candidates found, eligibility results, duplicates merged, screenings dispatched; manual trigger (admin) |
| `POST /assessments/{id}/feedback` | Memo feedback from readers |

In the Research app, companies found by sourcing carry `trigger = discovery` and appear in Companies with a "Found by agents" filter; discovery never puts a company in front of a reviewer without a completed screening.

**Events added for due diligence** (research audience unless noted; events about private documents, private findings and Level 3 reports go only to deal-team members): `domain.status_changed` (`assessment_id, revision, domain_id, status, gate_result`), `contradiction.detected` (`assessment_id, contradiction_id, domain_ids`), `document.status_changed` (`document_id, version, status: uploaded | scanning | rejected | quarantined | parsing | classified | needs_validation | ready | failed, reason`), `financials.validation_required` and `financials.validated` (`financial_table_id, version, issue_count`), `risk.updated` (`risk_id, severity, status`), `information_request.updated` (`request_id, status`), `report.version_created` (`report_version_id, level, revision`). Revisions opened by upgrade use `assessment.revision_created` with reason `upgrade`.

**Memo compatibility.** The report replaces the memo, but the memo names stay in the API for compatibility: `memo_version_id` (in `ReviewTarget`, feedback and events) holds the `report_version_id` of the report under review; `GET /assessments/{id}/memo` returns `MemoOutput` built from report sections 1, 14, 19 and 20; `/memo.pdf` redirects to `/reports/{version_id}?format=pdf`; `MEMO_READY` is the lifecycle state reached when a `ReportVersion` is stored; `assessment.memo_ready` is emitted together with `report.version_created` (same `version_id`). New clients use the report names; the aliases are removed only in a future major API version, recorded in the change log.

**Progress and stages.** Lifecycle states are unchanged except for `INFORMATION_REQUESTED`. Finer steps are stages, not states, and are reported as `stage` on `AssessmentSummaryView`, `run.state_changed`, `run.stage_started` and `run.stage_completed`:

| State | Stages inside it |
| --- | --- |
| `PLANNING` | `planning` |
| `RESEARCHING` | `ingesting_documents`, `domains_running`, `awaiting_validation`, `follow_up_research` |
| `VALIDATING` | `domain_gates`, `cross_domain_check`, `evidence_freeze` |
| `EVALUATING`, `CRITIQUING` | `evaluating`, `critiquing` |
| `MEMO_READY` | `report_writing`, `report_ready` |

`assessment.progress` payload: `{ assessment_id, revision, stage, domains_complete, domains_total, documents_ready?, documents_total? }`. The earlier `questions_answered` and `questions_total` remain in the payload for one major API version and count research questions across all domains.

**Domain configuration API.** `GET /config/domains` returns the effective `DomainConfig` list and overrides for the current configuration version. `PUT /config/domains` (owner or admin, `Idempotency-Key`) validates the full list, refuses to disable `thesis_fit` (`422 DOMAIN_REQUIRED`), creates a new configuration version and emits `config.version_created { version, changed: ["domains"] }`. Running assessments keep their pinned version.

**Waiting for financial validation.** Default is **non-blocking**: when a table needs validation, the financials domain completes with gate `partial` and reason `validation_pending`, calculations that depend on the table are `not_computable`, and the revision continues to its report. Validating the table later (Update `validate_financial_table(financial_table_id, version)` on the assessment workflow, or `POST /financial-tables/{id}/validate`) starts a `new_evidence` revision automatically; the existing report never changes. A deal team may set `validation_mode: "blocking"` on an assessment: the financials child then waits on the Update with a durable timer while other domains continue, holding no budget (reservations are settled or released before waiting and re-made on resume). In both modes: reminder to the deal team after 24 hours, escalation to the deal-team partner after 72 hours, and after 7 days the pending table is marked `validation_timeout` (in blocking mode the domain then completes `partial` with that reason). Cancelling the assessment cancels any wait cleanly. The stage `awaiting_validation` is shown only in blocking mode.

**Endpoints added for due diligence**

| Method & path | Purpose |
| --- | --- |
| `POST /companies` (field `level`), `POST /assessments/{id}/upgrade { level }` | Start at a level; upgrade to a higher level as a new revision |
| `GET /assessments/{id}/domains` | Domain status, gate result, coverage; POST /assessments/{id}/domains/{domain\_id}/retry reruns one failed or partial domain inside the same revision |
| `GET`, `PUT /assessments/{id}/deal-team` | Deal-team membership |
| `GET`, `PUT /workspace/external-ai-policy` (D1, owner or admin with step-up) | Owner accepts the provider data-processing terms for Level 3 |
| `POST /assessments/{id}/documents` (multipart, `Idempotency-Key`), `GET /assessments/{id}/documents`, `GET /documents/{id}/versions/{v}`, `DELETE /documents/{id}/versions/{v}`, `POST /documents/{id}/classification` | Data room |
| `GET /assessments/{id}/financials`, `GET /financial-tables/{id}`, `POST /financial-tables/{id}/corrections`, `POST /financial-tables/{id}/validate` | Normalized tables, validation queue and corrections |
| `GET /assessments/{id}/calculations` | `CalculationResult` list with inputs |
| `GET /assessments/{id}/risks`, `PATCH /risks/{id}` | Risk register; status and owner changes are audited |
| `GET /assessments/{id}/contradictions`, `POST /contradictions/{id}/notes` | Contradiction review; notes are audited and never delete evidence |
| `GET`, `POST /assessments/{id}/information-requests`, `PATCH /information-requests/{id}` | Missing-document requests and status |
| `GET /assessments/{id}/reports`, `GET /reports/{version_id}?format=web\|pdf\|docx\|json` | Report versions and exports |

New error codes: `415 UNSUPPORTED_FORMAT`, `422 UPLOAD_REJECTED` (validation failed, with reason), `422 MALWARE_DETECTED`, `403 LEVEL_NOT_ALLOWED`, `403 NOT_ON_DEAL_TEAM`, `403 EXTERNAL_AI_NOT_AUTHORIZED`, `409 VALIDATION_REQUIRED` (calculation requested on unvalidated data).

**Endpoints and errors added by D1–D6.**

| Method & path | Decision | Purpose |
| --- | --- | --- |
| `GET`, `PUT /workspace/external-ai-policy`; `POST /workspace/external-ai-policy/local-model/verify` | D1 | Read or change the policy; probe the local model |
| `GET /workspace/external-transmissions` | D1 | Audit list (metadata only) |
| `GET`, `PUT /workspace/retention` | D2 | `retention_days_after_closure` (0–90) |
| `GET /data-rooms/{id}/retention`; `POST /data-rooms/{id}/deletion-requests`; `POST`, `DELETE /data-rooms/{id}/legal-holds/{hold_id}`; `POST /data-rooms/{id}/retention-extension` | D2 | Retention record, immediate deletion, holds, one audited extension |
| `GET /sanctions/datasets`; `POST /sanctions/datasets/refresh` (admin) | D3 | Dataset versions and manual refresh |
| `GET /assessments/{id}/screening`; `PATCH /potential-matches/{id}` | D3 | Screening run and review decisions |

Errors: `403 EXTERNAL_AI_NOT_AUTHORIZED`, `403 PRIVATE_DATA_EGRESS_BLOCKED`, `409 LEGAL_HOLD_ACTIVE`, `410 DELETED`, `409 EXTENSION_ALREADY_USED`, `422 RETENTION_OUT_OF_RANGE`, `409 SANCTIONS_DATA_UNAVAILABLE`, `403 COMPLIANCE_ROLE_REQUIRED`. Events: `external_ai_policy.changed`, `external_ai.denied` (console), `data_room.deletion_scheduled`, `data_room.deleted`, `data_room.deletion_failed`, `legal_hold.changed`, `sanctions.dataset_updated`, `sanctions.dataset_failed`, `screening.completed`, `potential_match.updated`.

## Security inside the agent layer

Security is judged by forbidden effects not happening, not by how many malicious pages a classifier catches (P1-02). The controls below hold even when detection misses a payload.

1. **Instruction isolation.** Web pages, snippets, PDFs, READMEs, tool output and retrieved memory are only ever passed as data blocks inside user-role content. They are never merged into system or developer messages, and model output is parsed into fixed schemas, so injected text cannot add fields, tools or decisions.
2. **Tools authorized outside the model.** `ToolRegistry` checks role, capability queue, tenant scope and argument schema on every call. Agents have no tool that approves reviews, edits rubrics or reads secrets, so an injected instruction to do so has nothing to call. The classifier stays as defence in depth and quarantines flagged sources from context.
3. **Hardened SafeFetcher.** Only `http`/`https`, no embedded credentials. It resolves DNS, blocks private, loopback, link-local, CGNAT, multicast and metadata ranges for IPv4 and IPv6, then connects to the resolved IP so DNS rebinding cannot swap the target. Every redirect hop is re-validated (max 5). Responses are capped at 5 MB after decompression, with a decompression-ratio limit and a content-type allow-list. Fetch workers sit behind an egress proxy that enforces the same denylist at the network level. Playwright runs in a separate container with no credentials and downloads go to a scratch volume.
4. **Tenant authorization context (P1-09).** A `TenantContext` built from the authenticated principal is required by every repository, artifact read, cache key, vector query, Temporal client call, metric label and background job. PostgreSQL row-level security uses a per-transaction `SET LOCAL app.firm_id`, with policies that deny rows when it is unset, so pooled connections fail closed. Artifacts are served only after an authorization check on `artifact_id`; signed URLs are short-lived and issued after that check. Workflow IDs and traces from other tenants are never returned.
5. **Secrets.** The OpenAI key lives only in API and worker processes, from env or a secret manager, and supports rotation without restart. A log and trace processor redacts keys, tokens and email addresses, and CI scans logs from the E2E run for key patterns.

**Request limits.** JSON bodies are capped at 1 MB (`413 PAYLOAD_TOO_LARGE`); per-user rate limits apply to mutating endpoints (default 60 a minute) and submissions (default 20 an hour), returning `429 RATE_LIMITED` with `Retry-After`. Each user may hold at most 3 open event streams. Session cookies are `HttpOnly`, `Secure` outside development and `SameSite=Lax`; mutating requests also require a CSRF token, and CORS allows only the configured web origin.

**One network policy for every adapter.** The SafeFetcher rules apply to HTTPX, the GitHub and EDGAR clients, the feed reader and the browser worker alike:

- **Allowed URLs:** only `http`/`https`, default ports unless a source policy allows another. URLs with userinfo are rejected, and hosts are normalized (IDNA, percent-encoding, IPv4-mapped IPv6, decimal and octal IP literals) before checking.
- **Connection checks:** connect only to the resolved and checked IP, with TLS verification always on. Proxy environment variables are ignored except the configured egress proxy.
- **Browser worker:** Chromium runs in its own container on a network whose only route out is the egress proxy. A request-interception layer applies the same allow-list to navigations, redirects, iframes, subresources, WebSockets and downloads, and service workers are disabled. Each tenant gets a fresh browser context, with CPU, memory and time caps per render, and temporary files are wiped afterwards.
- **Content limits:** a content-type allow-list (HTML, XHTML, plain text, PDF, RSS/Atom/XML, JSON for structured APIs), a 5 MB decompressed cap enforced while streaming, a decompression-ratio limit, and charset detection before normalization.
- **Prohibited:** CAPTCHA solving, proxy rotation to evade blocks, stealth fingerprints and login automation, in any adapter.

**Data lifecycle (P1-07).** Each source adapter ships a policy file: access terms, licensing, fetch cadence, caching, allowed transformations, excerpt display rights and retention. Public visibility is not treated as permission to redistribute. Tenants can export or delete their private configuration, notes, assessments, reviews and vector entries. Public snapshots are shared by reference, so deleting a tenant removes its references and private artifacts without destroying snapshots other tenants lawfully cite; unreferenced snapshots are purged by the retention job. Source takedowns mark snapshots `source_unavailable` and hide their excerpts. The adapter never bypasses logins, paywalls or CAPTCHAs.

## Deployment and first run

`docker compose up --build` is the only command a new user runs; it is tested like any other feature (P0-06). The stack starts in dependency order and every health check tests real readiness, not process existence.

| Service | Starts after | Ready when |
| --- | --- | --- |
| `postgres` (with pgvector) | — | `pg_isready`, the app database exists, the `vector` extension is installed |
| `temporal-db-setup` (one-shot) | postgres | Temporal schema at the pinned version |
| `temporal` | temporal-db-setup | Frontend service answers a namespace describe |
| `minio` + `minio-init` (one-shot) | — | Buckets (including the quarantine and data-room buckets), lifecycle rules and a non-root app user exist; no anonymous access |
| `searxng` (pinned image tag, internal network only) | — | `GET /search?q=test&format=json` returns 200 with parseable JSON (readiness only; see the canary) |
| `clamav` (official image with preloaded signatures, internal network only) | — | `clamd` answers PING on its Unix socket after loading signatures (startup can take minutes) |
| `egress-proxy` | — | Proxy answers its health endpoint and denies a request to a private address |
| `migrate` (one-shot) | postgres | Alembic at head; seed run under an advisory lock and keyed by name, so reruns create nothing new |
| `api` | migrate, temporal, minio | `/health/ready` passes all dependency checks |
| `worker-*` (discovery, fetch, research, verification, evaluation, monitoring, delivery; replay only with --profile ops) | api | Each queue reports at least one poller in `DescribeTaskQueue` |
| `worker-docs` (no network, read-only root, non-root) | api, clamav | Parses the bundled fixture PDF, DOCX, PPTX, XLSX and CSV files |
| `worker-browser` (Playwright, pinned Chromium) | egress-proxy, api | Renders the bundled fixture page; may be disabled with `BROWSER_ENABLED=false` |
| `seed-demo` (one-shot) | — | Demo workspace loaded through the real services, documents ingested by the real pipeline, `GET /system/status` reports `demo_workspace: ready`. Skipped when `DEMO_WORKSPACE=false`. (The former `fixture-web` service is removed from the default stack.) |
| `web` | api | A server-side fetch of `/system/status` succeeds |

**Readiness modes** shown in the UI header:

- `setup_required` — no key, or a configured model is unavailable. The UI works, existing data is browsable, live submission is blocked with instructions, and an "Explore the demo workspace" path is offered when it is seeded. No search API key is ever requested.
- `demo_ready` — no provider key yet, and the demo workspace is seeded. Everything a user sees comes from PostgreSQL through the real API and SSE stream; actions that need no model (decisions, table validation and corrections, risk and request updates, uploads through virus scan and parsing, exports) run for real. Steps that need a model stop with `PROVIDER_NOT_CONFIGURED` and a link to setup. Costs shown are the seeded runs' recorded costs, labelled as sample data.
- `live_ready` — key valid, models available, all queues polling, search functional.
- `degraded` — live, but a queue has no pollers, the provider is rate limiting, or search is degraded; affected actions are disabled with the reason.

### Real integrations and the demo workspace

**One code path.** Every shipped process (web, api, every worker, seed jobs) uses the real integrations: PostgreSQL, Temporal, MinIO, ClamAV, SearXNG, SafeFetcher with Playwright, GitHub, SEC EDGAR, OpenAI. There is no `DEMO_MODE` switch, no fake provider, no fixture web server and no browser-side mock layer in production builds. CI fails the build if the web bundle contains `msw` or any `mocks/` import, or if a production entrypoint can import `tests/` (import-linter).

**Demo workspace.** A separate firm, `frm_demo`, isolated by the same row-level security as any customer workspace.

1. **Seed job.** `seed-demo` runs after `migrate` (idempotent, advisory-locked). It reads the versioned seed set `seed/demo/` and writes it through the application services, not raw SQL, so every invariant and validator applies. The seed set is the fixture set published with the design prototype under `project/fixtures/dd/`: summaries, domains, findings, report, financial tables, risks, requests, domain config and the event history.
2. **Documents.** The seed set's demo documents are real small PDF, DOCX, XLSX, PPTX and CSV files. The seed uploads them through `POST /assessments/{id}/documents` as the demo user, so they go through ClamAV, `worker-docs` parsing, encryption and MinIO exactly like customer files. An EICAR test file and a macro workbook are included so the blocked states are real.
3. **Calculations.** The seed stores validated financial tables; `ddcalc` computes every `CalculationResult` at seed time. The seed never inserts a calculated number.
4. **Text.** Findings and report text for the fictional demo companies are authored seed content, labelled "Sample company" in the UI. They are stored as normal rows with `origin: "seed"`, and the report export watermark says "Sample data".
5. **Events.** The seed writes its event history through the transactional outbox, so the real SSE endpoint replays it; every later action emits real events.
6. **Reset.** `POST /demo/reset` (owner or admin of `frm_demo`) or `docker compose run --rm seed-demo --reset` reloads the workspace.

**Demo user.** The seed creates `demo@thesis.local` with role partner in `frm_demo` and membership of the Level 3 demo assessment's deal team; there is no password. The sign-in page shows "Explore the demo workspace" when `DEMO_WORKSPACE=true`; it calls `POST /auth/demo-session`, which issues a normal session cookie scoped to `frm_demo`, with a 4-hour lifetime, rate limited per IP. A second seeded user, `demo-analyst@thesis.local`, is outside the deal team so restricted views can be shown. Demo sessions cannot read any other firm, cannot change providers, users or retention, and cannot create API tokens. Production deployments can disable the workspace with `DEMO_WORKSPACE=false`, which also disables the demo-session endpoint (404).

**What is real in the demo.** Reads, filters, exports, decisions (recorded against the seeded report version), table corrections and validation (start a real `new_evidence` revision; model steps then stop at `PROVIDER_NOT_CONFIGURED` until a key exists), risk and request updates, uploads (scan and parse for real), domain configuration changes. Starting new diligence works once OpenAI is configured; then it is ordinary live work in `frm_demo`.

**Tests.** Unit tests may use test doubles and are labelled `unit`; they never count toward a gate or feature completion. Integration, end-to-end and acceptance suites run against the full Compose stack with real services, the real OpenAI API (cost-capped CI secret), real SearXNG with its upstream engines, and real public sources (SEC EDGAR, GitHub, and a pinned list of stable public pages). UI tests drive the real web app against the real API with the demo workspace seeded; there is no MSW and there are no event-injection endpoints. Every test record states `environment: real` or `environment: unit`, and only `real` results can mark a feature complete.

## Approved decisions D1–D6

These six decisions are approved defaults (2026-11-07). This section is canonical for them; other sections and tabs refer here. Status vocabulary: **Decided** (approved), **Specified** (contract documented), **Implemented** (working code exists), **Tested** (relevant tests actually ran and passed), **Verified** (required end-to-end behaviour demonstrated). No application code exists yet, so no decision is Implemented, Tested or Verified. Harness runs recorded below test the specification's algorithms and fixtures, not the product.

| ID | Decision | Status |
| --- | --- | --- |
| D1 | External AI processing of private documents is off by default | Decided · Specified |
| D2 | Data-room retention: 90 days after assessment closure | Decided · Specified |
| D3 | Sanctions screening from official OFAC data (SDN + consolidated non-SDN) | Decided · Specified |
| D4 | Local Tesseract OCR as automatic page-level fallback | Decided · Specified (harness ran: 12/12 passed) |
| D5 | Project licence Apache-2.0 | Decided · Specified |
| D6 | False-claims test site on project-controlled GitHub Pages | Decided · Specified · **Pending deployment and verification** (fixture site built and checked locally: 7/7 passed) |

### D1 — Private documents and external AI

**Decision and rationale.** Private documents stay inside the self-hosted deployment unless a workspace owner or admin explicitly enables external AI processing for named data categories. Funds share data rooms under confidentiality obligations; the safe default is no transmission. This replaces the earlier "private-processing acknowledgement" design, which allowed Level 3 to send excerpts once acknowledged.

**Configuration (per workspace, versioned, audited).**

```python
PrivateDataCategory = Literal[
    "document_text_excerpts",     # passages from uploaded documents
    "document_tables",            # extracted financial and cap-table cells
    "document_images",            # page images (only relevant to a future cloud OCR adapter; none shipped)
    "document_metadata",          # filenames, titles, authors
    "private_findings",           # findings, risks, notes derived from private evidence
    "embedding_inputs",           # private text sent for embedding
]
AIPurpose = Literal["extraction", "verification", "evaluation", "critique", "report_writing",
                    "monitoring", "embeddings"]

class LocalModelConfig(BaseModel):
    base_url: AnyHttpUrl              # must resolve to a Compose service or RFC 1918/loopback address
    chat_model: str
    embedding_model: str | None = None
    api_key_secret_ref: str | None = None   # Docker secret name, never the value
    max_context_tokens: int
    verified_at: datetime | None       # set by the startup probe (structured-output test)

class ExternalAIPolicy(BaseModel):
    workspace_id: UUID
    version: int
    external_processing_enabled: bool = False
    provider: Literal["openai"] | None = None          # the only external provider supported for private data
    allowed_categories: frozenset[PrivateDataCategory] = frozenset()
    allowed_purposes: frozenset[AIPurpose] = frozenset()
    provider_terms_reference: str | None = None       # data-processing terms the admin reviewed (URL + version)
    authorized_by: UUID | None = None
    authorized_at: datetime | None = None
    expires_at: datetime | None = None                # default authorized_at + 365 days; then treated as disabled
    private_model_route: Literal["none", "local", "external"] = "none"   # derived, never set directly
    local_model: LocalModelConfig | None = None
```

Defaults: `external_processing_enabled=false`, no categories, no purposes, no local model. `private_model_route` is `local` when a verified local model exists, `external` only when external processing is enabled and unexpired, otherwise `none`.

**Authorization rules.**

- Only `owner` or `admin` may change the policy, after step-up re-authentication within the last 10 minutes.
- The consent screen names the provider, the categories, the purposes, the terms reference and the expiry. The admin types the workspace name to confirm.
- Each change creates a new version and an audit event `external_ai_policy.changed` (old and new values, actor, reason).
- Revocation takes effect immediately for new requests. Requests already in flight are not retried externally.
- Partners, analysts, operators and demo sessions cannot change the policy. The demo workspace is fixed at `external_processing_enabled=false`.

**Enforcement points (fail closed).**

1. **Classification at assembly.** The Context Assembler builds every model input as typed segments, each tagged `scope: public | private` and, if private, a `PrivateDataCategory` and the source `document_id`/version. Untagged text is treated as private `document_text_excerpts`.
2. **`PolicyEnforcedProvider`.** This is the only class allowed to construct an OpenAI or OpenAI-compatible client (import-linter contract). Every call goes through it: chat, structured output, embeddings, retries, critic rounds, background re-embedding, monitoring and reassessment. Before each request it loads the current policy (cache at most 30 s, invalidated by outbox event) and decides per request:
   - all segments public: the configured external provider;
   - any private segment and `private_model_route=local`: the local model only;
   - any private segment and route `external`: allowed only if every segment's category and the call's purpose are allowed;
   - otherwise deny with `EXTERNAL_AI_NOT_AUTHORIZED` (non-retryable Activity error). No partial sending, and no stripping of private segments to "make it fit" unless the calling step declares a public-only variant.
3. **Search and fetch egress guard.** `web_search` and `fetch_page` refuse any query or URL derived from private evidence. The guard is a per-assessment index of 8-word shingles of private spans plus the provenance tags on the query builder's inputs; a hit returns `PRIVATE_DATA_EGRESS_BLOCKED`. Private text is never sent to SearXNG, GitHub, EDGAR, Companies House or any other third party. URLs found only inside private documents are not fetched unless a deal-team member approves them individually.
4. **Activities carry references only.** Temporal payloads hold IDs, never document text. A payload codec rejects payloads over 2 KB that contain private-tagged strings, so retries and histories cannot leak content.
5. **Logs and traces.** Prompts and responses involving private segments are never logged. OpenTelemetry spans record only the segment counts and categories.
6. **Network.** `worker-docs` has no internet route. Workers that call the external provider go through the egress proxy, which allows only the configured provider host. The network layer is defence in depth; the policy decision is made in `PolicyEnforcedProvider`.

**Audit.** Every authorized external transmission writes an `ExternalTransmission` row: `transmission_id, workspace_id, assessment_id, revision, policy_version, provider, model, purpose, categories, segment_count, char_count, payload_sha256, operation_id, at`. It never stores content. Denials write `external_ai.denied` with the same metadata and the reason.

**Local model alternative.** `OpenAICompatibleProvider` targets an internal endpoint (for example vLLM, Ollama or llama.cpp server as an optional Compose profile `--profile local-llm`). The startup probe checks reachability, JSON-schema structured output on a fixed test prompt, and context length. It sets `verified_at`, or marks the route unavailable with the reason. If `base_url` resolves outside private address space, it is treated as external and refused for private data unless external processing is authorized.

**Effect on Level 3.** Level 3 no longer requires consent to start. Without an allowed private route, Level 3 still runs ingestion, virus scan, OCR, table extraction, validation, `ddcalc`, sanctions screening and the deterministic contradiction rules. Model steps on private data are skipped with reason `external_ai_not_authorized`, and the affected report sections are `incomplete` with that reason. The UI shows which steps were skipped and how to enable a local model or external processing.

**Failure behaviour.** A missing, expired or unreadable policy, a failed classification, policy-store timeout or an unverified local model all lead to denial, never to a fallback to the external provider. Public-only work continues.

**Tests:** D1-01 to D1-12 in the testing tab.

**Acceptance criteria.**

- With default settings, a full Level 3 run on the demo data room makes zero requests carrying private segments to any external host. This is shown by egress proxy logs and by `ExternalTransmission` being empty.
- Every model-calling code path is covered by an enforcement test.
- Revocation stops external private requests within 30 s.

### D2 — Data-room retention

**Decision and rationale.** Private material is deleted 90 days after the assessment closes. Administrators may only shorten the period. Legal holds and immediate deletion are supported. This minimizes exposure while leaving time for post-decision questions. It replaces the earlier "firm-set, 180 days" proposal.

**Configuration.** `retention_days_after_closure: int = 90`, allowed range 0–90 (0 = delete at closure), per workspace. Changing it applies to data rooms whose deadline has not passed, and only shortens deadlines; it never lengthens one.

**Closure and states.** An assessment is closed when it reaches `COMPLETED`, `REJECTED` or `CANCELLED`. `INFORMATION_REQUESTED` and `AWAITING_REVIEW` are not closed. Each data room carries a retention record:

```python
class RetentionRecord(BaseModel):
    data_room_id: UUID
    state: Literal["active", "scheduled", "on_hold", "deletion_requested", "deleting", "deleted", "deletion_failed"]
    first_closed_at: datetime | None
    delete_after: datetime | None      # first_closed_at + retention_days; fixed once set
    hold_ids: list[UUID] = []
    extension: RetentionExtension | None = None   # explicit, audited, see reopening
    deleted_at: datetime | None = None
    crypto_erasure_complete_at: datetime | None = None   # deleted_at + backup retention
```

**Reopening never resets or extends the clock.** `delete_after` is set at first closure and never recomputed. Reopening an assessment (new revision) keeps it, and the UI shows the remaining days. To keep documents longer, an owner or admin must record an explicit `RetentionExtension` (reason, new date at most 90 days after the reopening, audited). Only one extension is allowed per data room, and a legal hold is the only route beyond that.

**Legal hold.** Owner or admin, with a reason and an external reference. A hold blocks scheduled and requested deletion; immediate deletion requests return `409 LEGAL_HOLD_ACTIVE` and are recorded. Releasing a hold is audited. If the deadline has passed, deletion starts on the next scheduler run.

**Immediate deletion.** `POST /data-rooms/{id}/deletion-requests` (owner, admin or the deal-team partner) starts deletion at once unless a hold exists.

**What is deleted.**

- every MinIO object version of originals, normalized text, OCR page images and scratch files, thumbnails and exported Level 3 reports;
- PostgreSQL rows for `DocumentVersion` content fields, `DocumentSpan`, financial tables, private calculations, embeddings, full-text vectors, and cached prompts and responses containing private segments;
- private findings, risks and notes, which are replaced by tombstones;
- private sections of report versions, which are redacted to "Content deleted under the retention policy on {date}" while section numbers, statuses and citation IDs stay;
- the data room's data key.

**Temporal workflows.**

- `RetentionSchedulerWorkflow` runs as a Temporal Schedule daily at 03:15 UTC. It selects records with `delete_after ≤ now` and no hold, and starts `DataRoomDeletionWorkflow` for each with ID `del:{firm_id}:{data_room_id}`. That ID makes duplicate starts no-ops.
- Activities, all idempotent and resumable:
  1. `mark_deleting` (revokes access at once; reads return `410 DELETED`)
  2. `delete_objects` (lists all versions and delete markers under the prefix, deletes in batches of 1,000, resumes from listing)
  3. `delete_rows` (per table, in batches)
  4. `tombstone_findings` and `redact_reports`
  5. `destroy_data_key`
  6. `verify`: the version listing for the prefix is empty, row counts are zero, a vector search returns nothing, and a full-text search for 20 sampled shingles returns nothing
  7. `write_deletion_certificate`
  8. emit `data_room.deleted`
- Retries are bounded (5 attempts, exponential backoff). Persistent failure sets `deletion_failed`, alerts the console, and keeps access revoked. A data room is never reported deleted before `verify` passes.

**Object storage versioning and backups.**

- The data-room bucket has versioning enabled, to protect against accidental overwrite. A lifecycle rule expires noncurrent versions after 1 day and removes expired delete markers. The deletion workflow still deletes every version explicitly.
- Database and object-store backups are kept at most `BACKUP_RETENTION_DAYS` (default 30, maximum 35).
- Wrapped data keys in backups are not usable once the key is destroyed in the live system, provided the master key is rotated at least every 30 days and old master keys are destroyed after `BACKUP_RETENTION_DAYS`. Until then, erasure is complete only when the last backup containing the wrapped key expires, so `crypto_erasure_complete_at = deleted_at + BACKUP_RETENTION_DAYS`. The UI and the certificate state that date.

**Audit metadata kept after deletion.** Data room ID, assessment ID, document count, total bytes, retention policy version, closure date, deadline, hold and extension history, actor, timestamps and the verification result. Filenames, hashes of contents and document text are not kept.

**Failure behaviour.** On storage or database outage, the workflow waits and retries; access stays revoked. On a verification failure, the record goes to `deletion_failed`, the console shows an alert, and the workflow is re-run after the fix. On a clock or scheduler outage, the next run catches up, because selection is by `delete_after ≤ now`.

**Tests:** D2-01 to D2-10.

**Acceptance criteria.**

- A closed assessment's data room is deleted and verified within 24 hours of its deadline, and nothing private is retrievable through the API, search, vectors or object storage.
- Reopening does not move the deadline.
- Holds block deletion.
- Re-running the deletion workflow is a no-op.

### D3 — Sanctions screening

**Decision and rationale.** The default sources are official U.S. OFAC public data, the SDN list and the consolidated non-SDN list, downloaded from OFAC's Sanctions List Service. These are free, authoritative and require no account. Other jurisdictions are optional. This replaces the earlier "OFAC, EU and UK by default".

**Sources (configuration `SANCTIONS_SOURCES`, default `ofac_sdn,ofac_cons`).**

| Source | Default file | Official location |
| --- | --- | --- |
| `ofac_sdn` | `SDN.XML` (standard XML, with aliases and addresses) | OFAC Sanctions List Service exports, listed at `sanctionslist.ofac.treas.gov` › SDN List |
| `ofac_cons` | `CONSOLIDATED.XML` | `https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/CONSOLIDATED.XML` |

- **Verification item V-D3-1.** On 2026-11-07, OFAC's consolidated page linked its exports under `https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/`. Its SDN page linked the same file names under a different host (`ofacwebdev.wc2h.treasury.gov/SlsPublicApi_hotfix/...`). The adapter must use the `sanctionslistservice.ofac.treas.gov` export path for `SDN.XML`, confirm before release that it serves the same data, and refuse any non-`treas.gov` host.
- The XSD files published alongside the exports are vendored and used to validate each download.
- The optional sources `eu_fsf`, `uk_sanctions_list` and `un_consolidated` ship disabled. Enabling one requires its official URL in configuration and its own adapter tests.

**Ingestion adapter (`SanctionsIngestWorkflow`, Temporal Schedule daily 06:00 UTC, plus manual refresh).**

1. Download over HTTPS through the egress proxy, with conditional requests (`If-None-Match` / `If-Modified-Since`).
2. Store the raw file in the public-data bucket.
3. Compute its SHA-256.
4. Validate against the XSD.
5. Parse the entries.
6. Write a new `SanctionsDataset` version atomically, so screening never sees a half-loaded list.
7. Keep the previous 30 versions.

```python
class SanctionsDataset(BaseModel):
    dataset_id: UUID
    source: Literal["ofac_sdn", "ofac_cons", "eu_fsf", "uk_sanctions_list", "un_consolidated"]
    source_url: HttpUrl
    retrieved_at: datetime
    publish_date: date | None          # from the file's publication information
    sha256: str
    record_count: int
    status: Literal["current", "stale", "failed", "superseded"]

class SanctionsEntry(BaseModel):
    dataset_id: UUID
    uid: str                           # the list's own identifier
    entry_type: Literal["individual", "entity", "vessel", "aircraft"]
    primary_name: str                  # original, unmodified
    aliases: list[str]                 # original, unmodified
    normalized_names: list[str]
    programs: list[str]
    dates_of_birth: list[str] = []
    nationalities: list[str] = []
    countries: list[str] = []

class ScreeningSubject(BaseModel):
    subject_id: UUID
    kind: Literal["individual", "entity"]
    name: str
    role: Literal["company", "founder", "executive", "board_member", "investor", "other"]
    country: str | None = None
    date_of_birth: str | None = None
    source_finding_ids: list[UUID]

class PotentialMatch(BaseModel):
    match_id: UUID
    subject_id: UUID
    dataset_id: UUID
    entry_uid: str
    matched_name: str                  # original list string
    score: Decimal                     # 0-100
    band: Literal["exact_normalized", "strong", "weak"]
    corroborating: list[str]           # e.g. "country matches", "date of birth differs"
    review_status: Literal["pending_review", "dismissed_false_positive", "escalated", "confirmed_by_compliance"]
    reviewed_by: UUID | None
    review_reason: str | None

class ScreeningRun(BaseModel):
    run_id: UUID
    assessment_id: UUID
    revision: int
    screened_at: datetime
    datasets: list[UUID]               # exact versions used
    status: Literal["completed", "completed_stale_data", "unavailable"]
    subjects: list[ScreeningSubject]
    potential_matches: list[PotentialMatch]
```

**Freshness.** A dataset is `current` if refreshed within 3 days. Between 3 and 7 days, screening runs but every result is labelled "dataset older than 3 days". After 7 days, or if no dataset was ever loaded, the result status is `unavailable` and never "no matches".

**Normalization.** Unicode NFKC, then transliteration to ASCII with `anyascii` (ISC licence; `unidecode` is excluded because it is GPL). Then casefold, remove punctuation, collapse whitespace, and for entities also strip legal-form suffixes from a versioned list. The original strings are always kept and shown.

**Matching.**

- Each subject is matched against `normalized_names` of entries of the same type (individual or entity), with RapidFuzz `token_sort_ratio` and `token_set_ratio`, taking the maximum.
- Bands: `exact_normalized` for normalized equality; `strong` for a score of 92 or more; `weak` for 85 to 91. Below 85 is not recorded.
- Dates of birth, nationality and country can add or contradict evidence in `corroborating`. They never clear a match automatically.
- Thresholds are configuration values (`SANCTIONS_STRONG=92`, `SANCTIONS_WEAK=85`). Changing them is a new configuration version.
- Expected false-positive handling: common names produce weak matches, and the review queue shows the corroborating attributes to make dismissal quick.

**Review workflow.**

- Every potential match starts `pending_review` and shows as "Potential match: requires human review".
- Deal-team members may dismiss a match as a false positive, with a required reason, or escalate it.
- Only users with the `compliance_reviewer` permission can mark a match `confirmed_by_compliance`.
- Every transition is audited.
- The system never states that a person or company is sanctioned. The report wording is limited to:
  - "{n} potential matches pending review";
  - "{n} reviewed and dismissed";
  - "No potential matches against OFAC SDN and consolidated lists as of {publish\_date} (retrieved {retrieved\_at})".
- The report carries the disclaimer: "Informational diligence aid, not a substitute for professional compliance review."

**Failure behaviour.** A download failure keeps the last good dataset and marks the source `failed` in health. An XSD validation failure discards the download. A record count more than 10% below the previous version needs operator confirmation before activation. Screening without a usable dataset returns `unavailable` with the reason.

**Tests:** D3-01 to D3-10 (synthetic list entries only; no real listed names in fixtures).

**Acceptance criteria.**

- Datasets record URL, retrieval time, publish date and hash.
- Every screening run names the exact dataset versions it used.
- No template or code path can call a subject "sanctioned" outside quoted list data.
- Stale or missing data is never reported as no match.

### D4 — OCR

**Decision and rationale.** Native text extraction first. Local Tesseract OCR runs automatically only for pages whose native text is missing or unusable, inside the `worker-docs` sandbox. Scanned diligence documents are common, and local OCR keeps them private. This replaces the earlier "OCR off by default".

**Parser selection.**

| Detected type | Native extractor | OCR fallback |
| --- | --- | --- |
| PDF | pypdf per page; pdfplumber for tables | per page, when the page needs OCR (below) |
| PNG, JPEG, TIFF (new: now accepted) | none | whole image (TIFF: each frame counts as a page) |
| DOCX, PPTX | python-docx, python-pptx | embedded images not OCR'd by default (`OCR_EMBEDDED_IMAGES=false`) |
| XLSX, CSV | openpyxl, csv | never |

**When a PDF page needs OCR (defaults, configurable).**

- The native text has fewer than 50 non-space characters (`OCR_MIN_NATIVE_CHARS`).
- Or the text layer is garbled: more than 10% of non-space characters are symbols, private-use, unassigned, control or replacement characters (or `(cid:N)` runs) (`OCR_MAX_GARBAGE_RATIO`); or fewer than 50% of tokens look like words (`OCR_MIN_WORD_RATIO`).
- Or images cover at least 60% of the page and there are fewer than 200 native characters (`OCR_IMAGE_COVERAGE`, `OCR_IMAGE_PAGE_TEXT_CEILING`).

The garbled-layer rule was refined while testing: a printable-character ratio alone missed broken font maps, which extract as "■" boxes that count as printable.

**OCR procedure.**

1. Render the page with pypdfium2 at 300 DPI, capped at 40 megapixels.
2. Run Tesseract (`--oem 1 --psm 3`) via pytesseract, with `image_to_data` for word confidences.
3. Languages come from `OCR_LANGUAGES` (default `eng`). Packs are installed at image build time with the build argument `OCR_LANGUAGE_PACKS`, and an unknown language fails at startup, not at run time.
4. Page confidence is the mean word confidence. A page under 60 is flagged `low_confidence`: findings from it are capped at `claim_confidence=low`, and financial tables from OCR pages always go to the validation queue.

**Provenance.** `DocumentSpan` gains `extraction_method` (`native_text`, `native_table`, `ocr`), `page_number`, `bbox`, `ocr_engine` (e.g. `tesseract@5.3.4`), `ocr_language`, `ocr_confidence` and `ocr_reason` (`native_chars_low`, `garbled_text_layer`, `image_dominated`). Document IDs and versions are unchanged. OCR output is stored as a derived artifact of the same document version.

**Limits.** Per document:

- size at most 50 MB;
- at most 500 pages in total and at most 200 pages OCR'd (`OCR_MAX_PAGES`);
- per-page OCR timeout 60 s;
- total OCR time per document 20 min;
- 2 GB memory per OCR process;
- 2 concurrent OCR processes per worker.

Pages beyond a limit are marked `ocr_skipped_limit`, and the document becomes `ready` with a coverage warning.

**Sandbox.** OCR runs in the `worker-docs` per-file child process: no network namespace, seccomp profile, read-only root, tmpfs scratch wiped after each file, and CPU, memory and time rlimits.

**No cloud OCR.** No cloud OCR adapter ships. Adding one would require D1 authorization for the `document_images` category.

**Failure behaviour.**

- A malformed PDF gives `PARSE_FAILED`; an encrypted one gives `ENCRYPTED_DOCUMENT`.
- An OCR timeout on a page gives `ocr_failed` for that page with the reason; the other pages continue.
- Tesseract missing or a language pack missing is a startup failure, and health reports `worker-docs` as degraded.

**Tests.** D4-01 to D4-12. The fixtures are deterministic and generated by script: native, scanned, mixed, image-dominated, captioned image page, garbled text layer, garbled-only page, noisy scan, malformed and encrypted.

**Harness run (2026-11-07 23:40 UTC).** 12/12 checks passed with Tesseract 5.3.4, pypdf 6.17.0, pypdfium2 5.15.1 and pdfplumber.

- Character error rate on the clean synthetic scans: 0.0.
- Mean page confidence: 95.4–95.8.
- Each OCR'd page took about 0.6–0.7 s.
- The first run of the garbled-only check failed, which led to the refined garbled-layer rule above.

This tests the specified algorithm and thresholds, not the product's `worker-docs` code.

**Acceptance criteria.**

- Native pages are never OCR'd.
- Scanned pages are OCR'd locally with provenance and confidence.
- Limits are enforced.
- No document leaves the sandbox.
- The same fixtures give the same outputs on every run.

### D5 — Licence: Apache-2.0

**Decision and rationale.** Apache-2.0 is permissive and has an explicit patent grant, so funds and vendors can adopt and modify the project. This replaces "maintainer chooses permissive or copyleft".

**Repository requirements.**

- `LICENSE` holds the exact Apache-2.0 text. CI compares it with the SPDX `license-list-data` `Apache-2.0.txt`, using the SPDX matching guidelines.
- `NOTICE`: "Open-Source VC Due Diligence Agent. Copyright 2026 The Open-Source VC Due Diligence Agent Authors" plus the attributions required by dependencies' NOTICE files.
- Every source file carries an SPDX header, `SPDX-License-Identifier: Apache-2.0`, checked by the `reuse lint` dev tool.
- Manifests: `pyproject.toml` has `license = "Apache-2.0"` and `license-files = ["LICENSE", "NOTICE"]`; `package.json` has `"license": "Apache-2.0"`; container images carry the label `org.opencontainers.image.licenses=Apache-2.0`.
- `THIRD_PARTY_NOTICES.md` is generated in CI.
- `CONTRIBUTING.md` uses the Developer Certificate of Origin (`Signed-off-by`), not a CLA.

**Dependency licence policy.**

- **Allowed in linked code:** Apache-2.0, MIT, BSD-2/3-Clause, ISC, PSF-2.0, PostgreSQL, Zlib, MPL-2.0 (file-level, unmodified), LGPL-2.1/3.0 (dynamically linked, unmodified, e.g. psycopg).
- **Denied in linked code:** GPL and AGPL, any version.
- **Assets:** OFL-1.1 for fonts (Geist), with the licence text bundled; CC0-1.0 and CC-BY-4.0 for data, with attribution.
- **Separate services:** SearXNG (AGPL-3.0), ClamAV (GPL-2.0) and the object store run as separate, unmodified upstream containers that the project references but does not modify or relink. This is aggregation and does not affect the project licence. The project's own images must not bundle GPL or AGPL libraries; system packages in images are listed in `THIRD_PARTY_NOTICES.md`.
- **Audit in CI:** `pip-licenses`, `license-checker` for npm, and `syft` plus `grype` SBOM for images. The build fails on a denied or unknown licence unless an exception with a written justification exists in `licenses/exceptions.yaml`.

**Known findings from this review (verify at pin).**

- PyMuPDF (AGPL): already excluded.
- `unidecode` (GPL): excluded, use `anyascii`.
- trafilatura: pin a release published under Apache-2.0; earlier releases were GPL.
- python-docx: MIT; the earlier "licence UNVERIFIED" note is replaced by the CI check.
- selectolax 1.0: MIT; use the `lexbor` backend, because the Modest backend now raises an ImportError (seen during this review).
- pypdfium2: Apache-2.0 or BSD-3-Clause; PDFium BSD-3-Clause.
- Tesseract and pytesseract: Apache-2.0.
- MinIO: AGPL-3.0 service; see blocker B1.

**Redistribution obligations (documented in README).** Include `LICENSE` and `NOTICE`; mark modified files; keep third-party notices; no trademark grant; the patent grant terminates for anyone who sues over patents in the work.

**Bundled content.**

- Demo seed data, test fixtures (including D4 and D6) and screenshots are synthetic and project-authored, released as CC0-1.0, recorded in `fixtures/PROVENANCE.md`.
- No third-party web pages, logos, reports or real company documents are copied into fixtures.
- Real-world lists such as OFAC data are downloaded at run time, never committed.

**Failure behaviour.** A licence gate failure blocks merge. A newly discovered conflict is reported with a compatible replacement proposal, never solved by changing the project licence.

**Tests:** D5-01 to D5-06.

**Acceptance criteria.**

- The licence gate passes with zero unexplained exceptions.
- Every file has an SPDX header.
- Manifests and image labels agree.
- Fixture provenance is complete.

### D6 — Project-controlled false-claims test site

**Decision and rationale.** A real HTTPS site that the project controls, on GitHub Pages, publishes a clearly labelled synthetic startup page full of false and contradictory claims, plus separate synthetic evidence pages. It tests the whole public-research path without relying on any real company.

**Hosting contract.**

- Repository: `<owner>/vc-dd-test-fixtures` (public). Site path `/false-claims/`. Expected URL `https://<owner>.github.io/vc-dd-test-fixtures/false-claims/`.
- Pages served from a GitHub Actions deployment of the `site/` folder. "Enforce HTTPS" is on.
- The repository is Apache-2.0 for code and CC0-1.0 for content.
- Configuration: `FALSE_CLAIMS_TEST_URL` (no default; the live test is skipped with a clear message when unset) and `FALSE_CLAIMS_FIXTURE_VERSION`.

**Fixture content (built: `d6-false-claims@1.0.0`).**

- The company is "Plinthwick Synthetic Analytics", a name checked to have no real-company matches.
- Company-controlled pages:
  - `index.html` claims a founding year of 2016, a $48M Series B, more than 1,200 enterprise customers, SOC 2 Type II and 99.99% forecast accuracy, and carries a hidden prompt-injection line;
  - `about.html` claims a 2019 founding year and an unverifiable PhD from a fictional university.
- Independent evidence pages under `evidence/`:
  - a synthetic registry: incorporated 2023-03-14;
  - a synthetic securities filing: $2.1M seed only;
  - a synthetic auditor confirmation: 37 customers;
  - a synthetic assurance registry: no SOC 2 report.
- Every page carries a visible "SYNTHETIC TEST DATA" banner, `noindex, nofollow`, and the fixture version.
- `robots.txt` disallows crawling.
- `manifest.json` lists every claim with its expected outcome: contradictory for C1, C1b, C2, C3 and C4; missing (unsupported) for C5 and C6; injection flagged. It also lists file hashes.
- For the test run only, a test source-policy file registers the evidence pages as `public_record` sources. Discovery is by direct fetch of the configured URL; the pages are deliberately excluded from search engines.

**Required agent behaviour, asserted by test D6-03.**

- Fetch the page through SafeFetcher.
- Store an immutable snapshot with provenance.
- Treat the content as untrusted and flag the injection line.
- Extract C1–C6 as claims.
- Mark C1–C4 `contradictory`, citing the evidence pages, and C1b also against C1.
- Mark C5 and C6 `missing` (unsupported).
- Assign `claim_confidence` of low or medium.
- In the final report, none of the C1–C6 statements appears as a verified fact, and section 15 lists the contradictions.
- Scores and recommendation are identical with and without the injection line.

**Two test jobs.**

- **Normal CI** (`environment: ci-local`): the same files, byte-identical with hashes checked against the manifest, served by the `fixture-web` container. It runs under `--profile test` only, over HTTPS with a CI-generated certificate. It is deterministic and needs no internet.
- **Live job** (`environment: real`, explicitly enabled with `RUN_LIVE_D6=1`, nightly and before release): runs against `FALSE_CLAIMS_TEST_URL`. It first checks:
  - HTTPS returns 200 with a valid certificate;
  - the served manifest's `fixture_version` and hashes match the repository;
  - the GitHub API confirms the repository owner and the Pages source.

  It records the URL, repository, commit, fixture version and verification date in `tests/live/D6-verification.json`.
- D6 is Verified only after a passing live job.

**Current status.**

- Decided and Specified. The fixture site was built and its own checks ran: 7/7 passed (labelling, claims present, counter-evidence present, unsupported claims have no evidence, injection present, no real-world identifiers, deterministic hashes).
- **Deployment: pending.** The GitHub account available to this project's session is `jmpumuro`, with push access. No `vc-dd-test-fixtures` repository exists, and none was created. Publishing a public repository needs the owner's authorization.
- The candidate URL `https://jmpumuro.github.io/vc-dd-test-fixtures/false-claims/` is unverified and not deployed. No live test has run.

**Acceptance criteria.**

- The repository and URL are recorded, ownership is verified through the API, HTTPS is reachable, and the manifest hashes match.
- The ci-local test passes on every merge, and the live test passes at least once per release.
- The report never presents C1–C6 as verified.

### Remaining blockers

| ID | Blocker | Impact | Proposal | Needs |
| --- | --- | --- | --- | --- |
| B1 | MinIO's upstream repository was archived on 2026-04-25 after entering maintenance mode in late 2025. The Community Edition no longer publishes official binaries or container images (secondary sources; confirm at implementation). | Default object store has no maintained official image | Keep the S3 abstraction. Either (a) build and pin our own image from the last MinIO source tag (AGPL-3.0, unmodified, we own patching), or (b) switch the default to SeaweedFS (Apache-2.0), keeping MinIO as an alternative. Recommendation: (b), after an S3 compatibility run (versioning, lifecycle, SSE, multipart) | Human decision: storage default |
| B2 | D6 repository and Pages site not created | D6 cannot be Verified | Create `jmpumuro/vc-dd-test-fixtures` (or under an organization) and publish the built fixture | Owner authorization to publish a public repository |
| B3 | V-D3-1: OFAC SDN export host discrepancy | Wrong host could break ingestion | Use the `sanctionslistservice.ofac.treas.gov` export path; confirm `SDN.XML` there before release | Implementation check |
| B4 | No local model shipped for D1 | Without one, Level 3 model steps on private data are skipped by default | `--profile local-llm` with an OpenAI-compatible server; each firm chooses the model | Per-deployment choice |
| B5 | Licence versions to verify at pin (trafilatura, python-docx, anyascii, rapidfuzz) | Licence gate may fail | CI licence audit at first build | Implementation |

`/system/status` reports search separately: `search: { provider, state: ok | degraded | unavailable | disabled, json_enabled, engines: [{ name, state, suspended_until }], last_canary_at }`. Readiness (the endpoint answers JSON) and function (the hourly canary query returns non-empty, parseable results with usable URLs) are separate checks. If upstream engines are blocked, search is `degraded`, research continues with RSS and direct sources, and coverage records the gap.

The default workspace and an admin account are seeded only when `APP_ENV=development`. In any other environment the first owner is created through /setup with a one-time token, so no shared default credential reaches production. The README documents the exposed ports listed below, volumes, minimum resources (proposed 4 CPU and 8 GB RAM, to be measured), every environment variable in `.env.example`, and an optional `observability` profile. CI runs the stack from clean volumes, restarts it on the same volumes, and drives the browser journey against fixtures; a real-provider smoke test is opt-in and cost-capped.

**Sample workspace.** The seed also creates `frm_sample`, a read-only workspace with pre-generated fixture assessments covering every state the UI can show (ready for decision, contradiction, blocked, budget exhausted, completed). Every user is granted read access, so "Explore with sample data" works in any mode, including `setup_required`, with no provider and no agents running. Writes to it return `403 FORBIDDEN`, and it is excluded from usage and cost totals.

**Authentication.** Built in and self-hosted, with no external identity service required.

- **Accounts:** local accounts with Argon2id password hashes, server-side sessions in PostgreSQL, and an `HttpOnly` session cookie with CSRF protection.
- **First run:** on a fresh install the API prints a one-time setup token to its log. `/setup` uses it to create the first owner and firm (filling EDGAR\_USER\_AGENT from the firm name and owner email if it is blank), and the token expires on use or after 24 hours.
- **Development:** with `APP_ENV=development` a documented dev owner (`dev@localhost`) is seeded instead. Any other environment refuses to start with that account present.
- **SSO (optional):** OIDC is opt-in through `OIDC_ISSUER`, `OIDC_CLIENT_ID` and `OIDC_CLIENT_SECRET` (Authorization Code with PKCE), and works with any compliant provider; an optional `keycloak` Compose profile is provided for testing. Firm membership and roles always live in Thesis's own database.

**Service URLs.** Server-side code in `web` calls the API at `INTERNAL_API_URL=http://api:8000`. The browser uses `PUBLIC_API_URL=http://localhost:8000`, injected at runtime rather than baked into the bundle, so `http://api:8000` never reaches the browser. CORS allows only `PUBLIC_WEB_URL`, credentials are included, and the SSE stream uses the same origin rules.

**Exposed ports in development:** 3000 (web), 8000 (API), 8233 (Temporal UI, development profile only), 9001 (MinIO console, development profile only). SearXNG, PostgreSQL, Temporal gRPC and the egress proxy are reachable only on the internal network. Production profiles expose only the web and API ports.

## Testing gates per agent

Each agent ships with a fixture directory `tests/fixtures/agents/<role>/` holding recorded inputs, provider responses and expected outputs, used by unit tests only. A `FakeLLMProvider` replays them byte for byte for fast unit checks. Unit results never count toward a gate or toward feature completion; every gate is decided by the real-integration suites.

Tests assert persisted state, visible behaviour, schemas and security invariants; a test that only checks a mock was called does not count toward a gate.

| Gate | Minimum proof | Applies to |
| --- | --- | --- |
| A · Contracts | Pydantic/OpenAPI validation, malformed inputs, schema 1.x → 2.0 compatibility | Every agent, API, config, tool |
| B · Unit | Happy, edge and negative paths with deterministic fixtures | Every module |
| C · Integration | Real PostgreSQL, MinIO, Temporal and a local fixture web server | Persistence, adapters, workflows |
| D · Temporal | Retry, timeout, cancellation, replay of stored histories, worker restart, duplicate delivery | Every workflow and Activity boundary |
| E · Security | Tenant isolation, injection containment, SSRF and rebinding, secret redaction, authorization | All trust boundaries |
| F · Browser | Playwright drives real navigation against the API | Every user-facing feature |
| G · Documentation | Runnable example and configuration reference | Every public extension point |
| H · Independent verification | Lead or QA reruns the commands and records output and commit SHA | Every feature before VERIFIED |
| I · Clean install | `docker compose up --build` from empty volumes, then restart on the same volumes | Every release candidate |
| J · Quality evaluation | Versioned labelled corpus, measured regressions | Research, Verification, Evaluation, Critic, Memo |

External failures are produced by real means in the integration suite: Toxiproxy between workers and each dependency (OpenAI, SearXNG, PostgreSQL, MinIO, ClamAV) injects latency, resets and timeouts on real connections; `docker compose stop` takes services down; worker processes are killed with SIGKILL right after a provider call returns to test crash-after-success. The OpenAI key comes from a CI secret with a per-run cost cap. Guarantees that cannot be shown without provider cooperation, such as server-side request deduplication, are listed as not demonstrated.

**Test hooks.** When `APP_ENV=test`, the API mounts `/api/v1/test/*`: emit a catalog event for a subject, supersede a pending review with new evidence, drop or delay the event stream, inject a provider failure (`timeout`, `429`, `5xx`, `crash_after_success`), expire a reservation lease, and reset a tenant. These routes are absent in every other environment, and a startup check fails the API if they are present outside `test`.

**Provider scenarios.** The 20 release-blocking provider scenarios and the per-provider test cases live in the Provider tests tab. Examples include SearXNG with JSON disabled, all upstream engines blocked, exhausted GitHub quota, a browser render hitting a metadata endpoint, a malformed PDF, and an optional provider with no credentials. They are part of Gates C–F and I, and all are NOT\_RUN until a repository exists.

**Release-blocking scenarios**

| ID | Scenario | Expected result |
| --- | --- | --- |
| E2E-01 | Fresh checkout, clean volumes, `docker compose up --build` | All services healthy; real UI at localhost:3000 |
| E2E-02 | No OpenAI key | `setup_required`; UI works; demo workspace browsable through the real API; no paid calls |
| E2E-03 | Valid key (opt-in) | Live assessment reaches research and shows usage; key never exposed |
| E2E-04 | Same request submitted twice | One submission; identical response |
| E2E-05 | Intentional reassessment, same config | New `assessment_id`; prior one unchanged |
| E2E-06 | Two tenants research one company | Configs and private records isolated |
| E2E-07 | Worker dies after LLM success | Ledger policy followed; possible duplicate spend shown |
| E2E-08 | 20 tasks reserve the last budget | No overcommit; losers fail with `BUDGET_EXHAUSTED` |
| E2E-09 | Source changes after capture | Frozen snapshot still valid; new capture is a new version |
| E2E-10 | Tampered object or bad offsets | Provenance fails; claim cannot reach a finalized memo |
| E2E-11 | Two sources contradict | Both kept; conflict shown; uncertainty reflected |
| E2E-12 | Hostile page asks for tool call or secret | No unauthorized action occurs |
| E2E-13 | Redirect or DNS to a private address | Blocked; no internal access |
| E2E-14 | Cross-tenant artifact, vector or workflow access | Denied and audited |
| E2E-15 | Two reviewers decide concurrently | One decision applies; the other gets `409 REVIEW_ALREADY_DECIDED` |
| E2E-16 | Critical evidence arrives during review | Old target gets `409 STALE_REVIEW_TARGET` |
| E2E-17 | CRM write succeeds, acknowledgement lost | Retry creates no duplicate record |
| E2E-18 | Source times out or rate limits | Bounded retry; `degraded` visible; partial evidence kept |
| E2E-19 | Key missing or invalid mid-assessment | `BLOCKED_CONFIGURATION`; resume works; no retry loop |
| E2E-20 | Worker restart in research or review | Resumes; no decision lost |
| E2E-21 | Compatible deploy while awaiting approval | Workflow continues; replay deterministic |
| E2E-22 | Monitoring finds a material change | New revision; approved memo unchanged |
| E2E-23 | Reconciliation run twice after partial failure | Same final state; no duplicate effects |
| E2E-24 | Second startup on existing volumes | No duplicate seeds or migrations; no data loss |
| E2E-25 | Add the documented source adapter and criterion | Works end to end with typed contracts |

**Quality evaluation harness (P1-03).** A versioned corpus of frozen source snapshots with expert labels measures each property separately: citation validity, citation support precision, contradiction precision and recall, entity-resolution accuracy, research-question coverage, thesis-fit agreement with expert labels, memo factual error rate and uncited figures, decision stability when irrelevant sources change, and cost, latency and useful-evidence yield. Reports record corpus version, size, label provenance and confidence intervals, and a blind holdout set is kept out of prompt tuning. Earlier targets (support precision 0.90, contradiction recall 0.80) are provisional until a baseline is measured; quality gates are set from that baseline, while schema and security tests stay release-blocking from day one. The system is never tuned to imitate past investment decisions.

## Build sequence and ownership

Work runs in nine stages that keep the application runnable after each one; a stage ends only when its blocking scenarios pass in CI and tracker entries move to `VERIFIED`. No capability is dropped from scope.

| Stage | Deliverables | Lead specialists | Blocking proof |
| --- | --- | --- | --- |
| 1 · Contracts | ADRs; identity, review, provenance, ledger and budget schemas; lifecycle state machine | Architecture, Data, Temporal | Contract tests, schema review |
| 2 · Runnable shell | Compose, API, UI, Temporal, workers, migrations, seed, demo workspace seed and demo user, readiness modes, SearXNG with canary, built-in auth and /setup | Infrastructure, API, Frontend | E2E-01, 02, 24 |
| 3 · Durable execution | Agent runtime, capability queues, operation ledger, budgets, retry safety | Temporal, AI, Data | E2E-07, 08, 20 |
| 4 · Evidence | SafeFetcher, egress proxy, SearXNG adapter, HTML/PDF/feed extraction, browser worker, GitHub and EDGAR adapters, snapshots, provenance checks, citation resolver, entity resolution | Research, Security, Data | E2E-09 to 14 |
| 5 · Screening | Planner, Research, Verification, Evaluation, Critic, Memo, routing; Level 1 and Level 2 domain modules; gates; report schema and exports | AI, Temporal, QA | Live Level 1 screening against real public sources; Gate J on the real stack |
| 6 · Human review | Version-bound approval, review UI, audit; Level 3 data room, ClamAV, worker-docs parsers, ddcalc, financial validation queue, deal teams | API, Frontend, Temporal | E2E-15, 16 |
| 7 · Delivery and monitoring | Outbox delivery, watchlists, revision-based reassessment | Integrations, Temporal, Data | E2E-17, 22, 23 |
| 8 · Hardening | Tenant boundaries, rollout compatibility, retention, observability, recovery | Security, QA, Infrastructure | E2E-06, 14, 18, 19, 21 |
| 9 · Open-source release | README, Apache-2.0 LICENSE, NOTICE and licence gate (D5), contributor docs, examples, CI, clean install | Documentation, QA, Lead | All applicable E2E and gates |

**Delegation protocol.** The lead agent reads both planning documents and the repository first, then publishes a dependency graph, a file-ownership map and the contracts each stage touches. Subagents report changed files, migrations, tests added, commands run with actual output, risks and integration impact. The lead reruns tests after merging. If the environment cannot delegate, that is stated and the same work runs sequentially; delegation is never claimed when it did not happen. Work that needs secrets, a licence exception or external credentials stops and is reported.

**Tracker entry format** (`implementation-tracker.json`). Results link only to real logs, reports and commit SHAs; the values below are placeholders showing the shape, not results.

```json
{
  "id": "REL-E2E-01",
  "name": "Clean Compose startup and usable UI",
  "owner": "infrastructure-agent",
  "status": "TESTING",
  "dependencies": ["API-HEALTH", "WEB-APP", "TEMPORAL-WORKERS"],
  "required_gates": ["C", "D", "F", "H", "I"],
  "executed_gates": ["C", "F"],
  "results": {
    "C": { "status": "passed", "command": "<exact command>", "artifact": "<path or URL to captured log>" },
    "F": { "status": "passed", "command": "<exact command>", "artifact": "<path to Playwright report>" }
  },
  "not_applicable": {},
  "blockers": [],
  "verified_by": null,
  "verified_at": null
}
```

**Extension paths (P1-10).** The repository ships one worked, tested example of each:

- **Configure:** change thesis, rubric, model IDs and enabled sources through a new configuration version, with no Python edits.
- **Extend:** add a source adapter (with policy file, SafeFetcher rules, unit tests and a real-integration test against the live source), a new rubric criterion, and a new agent role (contract, prompt, capability queue, tool allow-list, fixtures) end to end.
- **Replace the model provider:** implement `LLMProvider` (model listing, structured output, error mapping, usage), register it in configuration, and pass the provider contract tests.
- **Customize the frontend:** change tokens and brand in one theme file, edit investor wording in `lib/status-copy.ts`, and add a page that uses the generated API client and the event provider.
- **Fork:** change a Temporal workflow with a `patched()` marker and a replay test proving old histories still run.

Alongside: README, `.env.example`, `docker-compose.yml`, architecture and configuration references, OpenAPI schema, troubleshooting, CONTRIBUTING, CODE\_OF\_CONDUCT and SECURITY. CI runs formatting, typing, unit, integration, workflow, security and browser suites on every pull request.

**Open risks**

- Model output drift between provider versions can break golden fixtures; pin model snapshots and re-record fixtures on upgrade.
- Contradiction detection grows quadratically; compare only claims sharing a subject and entity.
- Critic and Evaluator may converge on one model family; keep the default split and track agreement rate.
- Pre-seed companies have sparse public traction; expect high uncertainty and show it rather than fill gaps.
- Provider-side deduplication is not available to rely on, so some duplicate spend after crashes is unavoidable; it is surfaced, not hidden.

**Architecture invariants** (each enforced by code and a test)

1. Every assessment references exactly one immutable configuration snapshot.
2. A company can have many assessments; assessment IDs are independent of configuration version.
3. No finalized assessment, evidence snapshot or review decision is overwritten.
4. Every material claim has resolvable evidence or an explicit unverified, not-publicly-verifiable or unavailable status.
5. Citation offsets and hashes refer to the exact stored normalized snapshot.
6. Agent conclusions are never authoritative approvals.
7. Every external side effect has a stable operation ID and documented retry semantics.
8. Unknown external outcomes are recorded as unknown, not as failed or free.
9. Concurrent tasks cannot reserve more than the available budget.
10. Every tool call is authorized independently of what the model asked for.
11. Tenant isolation holds at every data and workflow boundary.
12. Approval applies only to the exact versions reviewed.
13. A missing OpenAI key never stops the UI or the demo workspace.
14. Workflows make no network, database or model calls.
15. Long-running workflows stay compatible across deploys or have an explicit migration.
16. Every released feature has reproducible, recorded verification evidence.

**Decisions to record in ADRs** — sensible defaults are proposed; the ones marked *maintainer* block release until chosen.

| Decision | Default (status) |
| --- | --- |
| Licence | Apache-2.0 (decided, D5). SearXNG (AGPL-3.0), ClamAV (GPL-2.0) and the object store run as separate unmodified services (aggregation); linked dependencies must pass the D5 licence gate. |
| Authentication | Built-in local accounts with first-run /setup; seeded dev owner only in development; OIDC optional (decided) |
| LLM provider | OpenAI via the official SDK; proposed models `gpt-6-luna` and `gpt-5.6-terra`, verified at startup (decided provider, models to verify) |
| Web search | Self-hosted SearXNG, no account; OpenAI hosted search, Tavily, Brave and Exa only as explicit opt-in adapters (decided) |
| Fetch and extraction | HTTPX + selectolax; Playwright fallback; pypdf for PDF (BSD-3-Clause); trafilatura (Apache-2.0) as an optional extractor (decided) |
| Review policy | `single-reviewer@1`; `quorum@1` available |
| Duplicate submissions | `reuse_active` by default; `new_assessment` and `reassess_latest` explicit |
| Default sources | Company websites, SearXNG web and news search, RSS feeds from the feed registry, public GitHub, SEC EDGAR. Each has a policy file. GDELT stays planned until its terms and limits are confirmed. *Maintainer* confirms the list |
| Embeddings | pgvector always present; embeddings on in live mode (OpenAI, model to verify), seeded vectors in the demo workspace, full-text fallback; private spans only via an allowed private route (D1) (decided) |
| Retention | Data-room content deleted 90 days after closure (decided, D2); other private configuration and assessments until the tenant deletes; unreferenced public snapshots purged after 180 days; JSON + artifacts export |
| Notifications and CRM | In-app notifications and local JSON/CSV export by default; SMTP, webhook, Slack, HubSpot, Salesforce optional (decided) |
| Observability | Structured logs always; OpenTelemetry collector, Prometheus, Grafana and Tempo in an optional profile; no hosted account (decided) |
| Resource profile | Proposed 4 CPU / 8 GB to be measured, plus about 1 GB for `worker-browser`; observability profile optional |

**Definition of done.** The project is VERIFIED only when all of these hold with saved evidence:

- [ ] Eight agents implemented with typed contracts and tested execution boundaries
- [ ] Durable workflows with parallel research, bounded replanning, human review and monitoring
- [ ] Identity, retry safety, atomic budgets, provenance and review-target corrections implemented
- [ ] Security holds independently of injection detection
- [ ] `docker compose up --build` gives a working UI at localhost:3000 with no extra commands
- [ ] API, migrations, Temporal, workers, object storage and seed initialize automatically
- [ ] UI usable without a key, and the demo workspace is served from the database through the real API
- [ ] OpenAI is the default configurable live provider; keys protected; live tests opt-in
- [ ] Every applicable E2E scenario passes with logs saved
- [ ] All tracker entries VERIFIED by independent review
- [ ] Configure, extend and fork paths documented and exercised
- [ ] Apache-2.0 LICENSE, NOTICE, SPDX headers and licence gate in place (D5); contributor and security docs complete
- [ ] Remaining limitations disclosed, not presented as done
