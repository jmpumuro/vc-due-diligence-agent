# Thesis UI — Implementation Prompt for the Coding Agent

Nov 7, 2026 · @Joe

**Scope update (2026-11-07).** The backend is now the Open-Source VC Due Diligence Agent. Everything below still applies; the section "Due diligence additions" at the end adds diligence levels, domains, the data room, financial validation, risks, contradictions, information requests and the 21-section report. Where this document says "memo", the backend serves a due diligence report: the memo names remain valid API aliases (see that section), so existing screens keep working while the new ones are built. Nothing here has been implemented or tested.

## Mission

Build the production web UI for Thesis as two apps in one Next.js service: the **Research app** for investors at `/` and the **Agent console** for operators at `/console`. Every screen reads real API data, every action calls a documented endpoint, and every live update arrives as a typed server event whose name and payload match the backend exactly.

**Sources of truth, in priority order**

1. [Open-Source VC Due Diligence Agent — Master Implementation Plan](https://claude.ai/artifact/Qwqmg6f2E3jvmmUMUkvnRh): domain models, API routes, lifecycle states, review target, readiness modes, the two-interface split and the status-copy table.
2. This document: UI architecture, design system, action contract and event contract.
3. The interactive prototype on the Thesis canvas (Diligence app and Agent console artboards): layout, hierarchy, copy and interaction details. A saved diligence-app export lives at `docs/prototypes/thesis-diligence-app.html`. Its data is the demo workspace seed set (`project/fixtures/dd/`), which is the same data the backend's `seed-demo` job loads into PostgreSQL; in the real app it arrives only through the API.

Where they disagree, follow the plan, then this document, and record the decision in an ADR. If the backend lacks an endpoint or event this document needs, stop and report it; do not invent a client-side workaround.

The prototype does not draw every page. Sourcing, Configuration editing, Audit log and Data and retention in the console, and memo feedback in the Research app, have no artboard; build them from the same shell, card, table and form patterns. The prototype's "Models and versions" page is the read-only half of Configuration.

**Non-negotiables**

- No hard-coded result data and no mock layer anywhere in the app. Every screen, including the demo workspace, reads from the real API and SSE stream. The build fails if the bundle contains `msw` or a `mocks/` import.
- TypeScript types for requests, responses and events are generated from the backend's published schemas, never hand-written. CI fails on drift.
- The UI never decides what happened. It shows a pending state after an action, then updates from the HTTP response and the confirming event.
- The Research app never shows operation IDs, queues, tokens, retries, digests or raw error codes. The console may.
- Analysts receive 403 on every `/console` route and every console API; the UI hides console links for them.
- A missing OpenAI key never breaks the UI; readiness modes drive what is enabled.
- Do not report work as done without the evidence required in the final section.

## Stack and structure

Next.js (App Router), TypeScript strict, Tailwind CSS with CSS-variable tokens, shadcn/ui primitives, TanStack Query for server state, `openapi-typescript` for API types, Zod schemas generated from the event JSON Schema, Vitest with React Testing Library, and Playwright. Pin versions in `package.json` and record them in the README.

```text
web/
  app/
    (diligence)/           # "/" — roles analyst, partner, admin, owner
      page.tsx             # Home
      companies/page.tsx   # list + Start diligence (level picker)
      companies/[companyId]/page.tsx        # latest assessment of the company
      companies/[companyId]/a/[assessmentId]/page.tsx   # tabs: report, domains, financials, dataroom, risks, contradictions, requests, sources, history (?tab=)
      decisions/page.tsx
      watchlist/page.tsx
      thesis/page.tsx
      settings/page.tsx    # external AI policy (D1), retention and holds (D2), domain configuration
    console/               # "/console" — roles operator, admin; guarded in middleware.ts
      page.tsx             # Runs
      runs/[assessmentId]/page.tsx          # tabs: timeline, domains, stages, ledger, budget, findings
      health/page.tsx
      costs/page.tsx
      reconciliation/page.tsx
      quality/page.tsx
      versions/page.tsx
    api/auth/...           # session handling only; no business logic in Next.js routes
  components/ui/           # shadcn primitives, themed
  components/shell/        # Sidebar, ProductSwitcher, TopBar, Breadcrumbs, CommandPalette, Notifications, ThemeToggle
  components/diligence/    # LevelPicker, LevelBadge, UpgradeButton, VerdictStrip, MeasuresRow, FindingKindBar, ReportView,
                           # SectionStatusChip, ExportMenu, DomainProgressTable, Dropzone, DocumentTable, ValidationQueue,
                           # TableGrid, MetricTable, RiskTable, RiskMatrix, ContradictionCompare, RequestList, DecisionCard,
                           # ExternalAIPolicyPanel, RetentionPanel, ScreeningReview, OcrBadge, DomainConfigTable, Restricted
  components/console/      # RunTable, RunGantt, DomainRunTable, LedgerTable, BudgetBullets, FindingsList, LiveEventTail, QueueHealth
  lib/api/                 # generated types + typed fetch client (adds Idempotency-Key, maps error codes)
  lib/events/              # EventStream provider, generated Zod schemas, query-invalidation map
  lib/status-copy.ts       # system state + stage → investor copy (from the plan)
  tests/                   # unit (components with recorded real API responses), contract, e2e against the real stack
```

- The browser talks only to the FastAPI backend at `PUBLIC_API_URL (injected at runtime, never baked into the bundle and never http://api:8000; server-side code uses INTERNAL_API_URL)` through the typed client; Next.js server components may prefetch with the user's session cookie.
- Role and tenant come from the session (`GET /api/v1/me` → `{ user, firm, roles }`), never from URL or local storage.
- One `EventStreamProvider` per tab opens the SSE connection described below and feeds TanStack Query.

## Design system

One token set serves both apps. The Research app defaults to light and the console to dark; each user's choice is saved per user via `PATCH /api/v1/me/preferences { theme }` and follows `prefers-color-scheme` until set. Define tokens as CSS variables on `:root` and `[data-theme="dark"]`, and map them in `tailwind.config.ts`.

| Token | Light | Dark | Use |
| --- | --- | --- | --- |
| `--bg` | #F6F6F7 | #0C0D10 | Page |
| `--surface` | #FFFFFF | #131418 | Cards, top bar |
| `--surface-2` | #F3F3F5 | #1B1C21 | Table heads, tracks, hovers |
| `--sidebar` | #FBFBFC | #0F1013 | Sidebar |
| `--border` / `--border-strong` | #E6E6EA / #D4D4DA | #25272D / #34373E | Dividers / inputs |
| `--text` / `--muted` | #18181B / #62626B | #EDEDEF / #A1A1AA | Text (muted passes 4.5:1 on both surfaces) |
| `--brand` / `--brand-soft` / `--brand-text` | #2E5BFF / soft cobalt wash / #1E3FCC | #5B7CFF / deep cobalt panel / #9BB0FF | Primary actions, selection, score marks (Ink & Cobalt; supersedes older purple #5146E5) |
| `--green` `--amber` `--red` `--blue` `--gray` | #16794A #A16207 #C2302A #2563EB #8E8E96 | #3FB871 #D9A23A #EF5A50 #5B8CFF #71717A | Status dots only; never the only carrier of meaning |

- **Type:** Bricolage Grotesque for display (Ink & Cobalt); Geist for UI body and Geist Mono for IDs/figures via `next/font`. Sizes 12 / 13 / 14 / 16 / 20 / 26, weights 400 / 500 / 600 / 700, tabular numbers on.
- **Shape:** radius 8 (controls), 10 (buttons, segmented tracks), 14 (cards). Borders 1 px; one soft shadow for cards, a stronger one for popovers and the palette.
- **Status pattern:** pill = dot + words. Colour reinforces, words carry meaning.
- **Motion:** 150 ms ease-out for hover and open; a pulse on "Live" indicators only; all motion disabled under `prefers-reduced-motion`.
- **Shell components:** Sidebar with sectioned icon nav and count badges, ProductSwitcher (Research / Agent console, hidden for analysts), TopBar with Breadcrumbs, search trigger opening the ⌘K CommandPalette, Notifications popover, ThemeToggle, primary action. Toasts bottom-right for action results.
- **Data components:** VerdictStrip (recommendation pill, conditions list, headline, coverage-limits line), MeasuresRow (four separate cells: source reliability split bar, claim confidence split bar, 12-cell domain coverage strip, attractiveness score with range band and advance line; never merged), FindingKindBar (seven kinds; segments and legend are buttons that filter Sources), DomainProgressTable, ReportView with SectionStatusChip, ContradictionCompare (two columns with URL or document locators), ValidationQueue with TableGrid, MetricTable, RiskTable with RiskMatrix, RunGantt (domain child workflows on one time axis; failed attempts and waiting on a person drawn distinctly), DomainRunTable, LedgerTable, BudgetBullets, LiveEventTail. The attractiveness rubric (formerly the Scorecard) appears only inside the report's thesis section, never as an overall score.
- **Responsive:** sidebar collapses to a top sheet under 900 px; tables scroll horizontally inside their card; charts keep printed numbers at every width.

## Screens

Each page lists what it loads and which events keep it fresh. All endpoints are under `/api/v1`. Summary views (`?view=summary`) return investor-safe fields only and are enforced server-side, not by hiding fields in the UI.

**Research app**

| Page | Loads | Live via events | Key components |
| --- | --- | --- | --- |
| Home | `GET /dashboard/summary?view=summary`, `GET /reviews?status=pending`, `GET /assessments?state=active&view=summary`, `GET /monitoring/events?limit=3` | `assessment.*`, `review.*`, `monitoring.event_detected`, `system.status_changed` | KPI row, decision list, in-progress list with Live indicator, what changed |
| Companies | `GET /companies?q=&status=&cursor=` | `assessment.created`, `assessment.state_changed` | Research form with policy choice, identity picker, filter chips, table |
| Company | `GET /companies/{id}`, `GET /assessments/{id}?view=summary`, `/claims?view=summary`, `/memo`, `/questions`, `/revisions` | `assessment.*` for this ID, `review.superseded` | LevelBadge, UpgradeButton, VerdictStrip, MeasuresRow, FindingKindBar; tabs Report / Domains / Financials / Data room / Risks / Contradictions / Requests / Sources / History (see Due diligence additions) |
| Decisions | `GET /reviews?status=pending` (each item carries its current `ReviewTarget` and digest) | `review.requested`, `review.decided`, `review.superseded` | DecisionCard with footer actions and problem callouts |
| Watchlist | `GET /watchlist`, `GET /monitoring/events` | `watchlist.updated`, `monitoring.event_detected` | Table with pause/resume, event feed |
| Thesis | `GET /config/current?scope=thesis` | `config.version_created` | Mandate editor, rubric weights; models and budgets link to the console |

**Field mapping for the company page.** Every visual reads `AssessmentSummaryView` from the plan; nothing is computed in the browser except layout.

| Component | Fields |
| --- | --- |
| VerdictStrip | `recommendation` (`advance \| hold \| pass \| inconclusive`), `conditions[]`, `headline`, `measures.*` (four cells), `level`, `stage`; "advance" with conditions reads "Advance, with conditions". Legacy `watch` and `insufficient_evidence` never appear in new responses; treat them as `hold` and `inconclusive` if met in old data. |
| Scorecard | `measures.attractiveness` (score, range, advance\_threshold) in MeasuresRow; `scorecard[]` only inside report section 3 as the attractiveness breakdown, with each row linking to its findings |
| EvidenceBar | `evidence_counts` (confirmed, partial, disagree, unverified); segment click sets the Sources filter to that group |
| Sources list | `GET /assessments/{id}/claims?view=summary`; label and group from the plan's claim-label table |
| ContradictionCompare | contradictions in the claims response: both claims, sources, trust tiers, dates, preferred claim |
| Domains (replaces Key questions) | `GET /assessments/{id}/domains` → `DomainStatusSummary[]`: `domain_id, status, gate_result, reason, sources_found, sources_required, findings, contradictions, risks, requests, can_retry`. Coverage cell reads "{found} found · {required} needed"; status dot uses `status`, the coverage bar uses `gate_result`. |
| How this was researched | `research_summary` |
| Decide button | shown when `can_decide`; otherwise "Waiting for a partner" |

**Coverage limits.** When the assessment has source gaps, the memo shows the backend's "Coverage limits" line directly under the headline, and the Sources tab lists blocked or unavailable sources with their reason ("site blocks automated access", "page not found", "web search was limited"). Never render an empty search as "no online presence".

**First-run setup.** `/setup` is the only unauthenticated page. It asks for the one-time setup token from the API log, a firm name, and the owner's email and password, then signs the owner in. The owner's email also fills the SEC EDGAR User-Agent. Once any user exists, `/setup` returns 404.

**Agent console**

| Page | Loads | Live via events | Key components |
| --- | --- | --- | --- |
| Runs | `GET /ops/runs?cursor=`, `GET /ops/attention`, `GET /system/status` | all `run.*`, `operation.updated`, `budget.*`, `system.status_changed` | KPI strip, Needs action list, run table, LiveEventTail |
| Run detail | `GET /assessments/{id}/workflow`, `/operations`, `/budget`, `/findings`, `/timeline` | events for this assessment | Timeline (RunGantt), Stages, Ledger, Budget, Findings tabs; actions bar; trace link per operation |
| Health | `GET /health/ready`, `GET /system/status` | `system.status_changed`, `queue.health_changed` | Dependencies (including SearXNG readiness, last canary result and per-engine state), queues with pollers, backlog and permissions |
| Costs | `GET /usage?from=&to=&group=role,day,certainty`, `GET /budgets` | `budget.*`, `operation.updated` (debounced) | KPI strip, daily spend vs cap, cost by role |
| Reconciliation | `GET /ops/reconciliation`, `GET /ops/outbox/summary` | `reconciliation.completed`, `outbox.delivery_changed` | Checks list, outbox summary, run button |
| Sourcing | `GET /ops/sourcing/batches`, `/ops/sourcing/batches/{id}` | `sourcing.batch_completed` | Batch table (found, eligible, duplicates merged, dispatched), batch detail with candidate eligibility, manual trigger (admin) |
| Quality | `GET /ops/quality/latest` | `quality.report_published`, `feedback.recorded` | Metrics with intervals and provisional thresholds; recent reader feedback |
| Configuration | `GET /config/current?scope=agents\|budgets\|sources\|review`, `GET /ops/versions` | `config.version_created`, `system.status_changed` | Models with availability, budgets, source policies, review policy; edit and save as a new version (admin); workflow builds and patches |
| Audit log | `GET /ops/audit?subject=&actor=&cursor=` | — (refresh on focus) | Filterable append-only table: time, actor, action, subject, before and after |
| Data and retention | `GET /tenant/members`, retention settings in `GET /config/current?scope=retention` | `export.ready` | Members and roles, export, deletion requests with status (owner only) |

`GET /assessments/{id}/timeline` returns stage and task spans `{ key, label, parent, started_at, ended_at, attempt, outcome: succeeded | failed | waiting }`; the Gantt renders exactly those spans and never infers timing.

## Action contract

Every mutating request sends an `Idempotency-Key` (UUID v4 created when the user commits the action and reused on automatic retry) and the CSRF token. After a 2xx the UI shows the response immediately and treats the listed event as confirmation; if the event has not arrived within 10 s it refetches the affected query. Error copy comes from `lib/status-copy.ts`, keyed by the codes in the backend's `schemas/errors.json`; a unit test fails if any code has no copy. Buttons for actions the caller's role cannot perform are not rendered; the server still enforces every permission.

**Research app**

| UI action | Request | Success → UI | Errors → UI copy | Confirming event |
| --- | --- | --- | --- | --- |
| Start research | `POST /companies` `{ name, domain?, policy: reuse_active \| new_assessment \| reassess_latest }` | `outcome` drives the callout: `created`, `reused_active`, `reassessment_created`; `identity_review_required` shows the candidate picker using `identity_candidates` and keeps `identity_request_id` | `422 PROVIDER_NOT_CONFIGURED` → "Live research needs setup first"; `409 IDEMPOTENCY_KEY_CONFLICT` → "This request changed; please submit again"; `429 RATE_LIMITED` → "Too many requests; try again in a minute" | `assessment.created`, then `assessment.state_changed` |
| Pick identity candidate | `POST /identity-resolutions/{identity_request_id}` `{ company_id \| null }` (null = new company) | Same as Start research | `409 RESOLUTION_EXPIRED` → "Please start again" | `assessment.created` |
| Advance / Pass / Ask for more research | `POST /assessments/{id}/review` `{ target, decision: approve \| reject \| request_research, comment?, idempotency_key }`; buttons render only when `can_decide` | Card shows the decision; Decisions badge decrements | `409 STALE_REVIEW_TARGET` → "This memo changed while you were reading it" + reload button; `409 REVIEW_ALREADY_DECIDED` → "{name} decided this a moment ago"; `403 REVIEW_NOT_AUTHORIZED` → "Your role can't decide this one; a partner needs to"; `409 REVIEW_EXPIRED` → "This review expired and was escalated" | `review.decided`; `request_research` also `assessment.revision_created` |
| Review the new version | `GET /reviews/{assessment_id}` | Card replaces target, score and summary | — | — |
| Give memo feedback | `POST /assessments/{id}/feedback` `{ memo_version_id, rating, reasons[], claim_ids[], comment? }` | Toast "Thanks — this helps us check quality" | `4``22 VALIDATION_FAILED` → field errors | none in the Research app (`feedback.recorded` goes to the console) |
| Watch / Pause / Resume | `POST /watchlist` `{ company_id, rules? }`; `PATCH /watchlist/{id}` `{ paused }` | Row updates; toast | `409 ALREADY_WATCHING` → "Already on your watchlist" | `watchlist.updated` |
| Save thesis | `POST /config/versions` `{ scope: "thesis", base_version_id, changes }` | Toast "Saved as version N; running reviews keep their version" | `422 CONFIG_INVALID` → field errors; `409 CONFIG_BASE_OUTDATED` → "Someone saved first" + diff; `403 FORBIDDEN` for analysts (editor is read-only for them) | `config.version_created` |
| Explore the demo workspace | `POST /auth/demo-session` (from the sign-in page or `/setup`) | Signs in as the seeded demo user (`frm_demo`); everything then loads from PostgreSQL through the real API. A banner says it is the demo workspace and offers sign-out. `404` when `DEMO_WORKSPACE=false` → hide the button. | — | — |
| Download PDF | `GET /assessments/{id}/memo.pdf` | File download | `404 MEMO_NOT_READY` → "The memo isn't ready yet" | — |
| Open notification / mark read | `POST /notifications/{id}/read` | Navigates to target | — | `notification.created` adds new items |
| Switch theme | `PATCH /me/preferences` `{ theme }` | Applied instantly, saved quietly | — | — |

**Agent console**

| UI action | Request | Success → UI | Errors → UI copy | Confirming event |
| --- | --- | --- | --- | --- |
| Resume blocked run | `POST /assessments/{id}/resume` | Row shows "resume sent" | `409 PROVIDER_NOT_READY` (button disabled while `system.status_changed.provider_state != ok`) | `run.state_changed` to the prior active state |
| Raise budget and continue | `POST /assessments/{id}/budget-overrides` `{ limit_usd, reason }` (admin) | New revision link | `403 FORBIDDEN`, `422 OVER_TENANT_CAP` | `budget.override_applied`, `assessment.revision_created` |
| Acknowledge possible duplicate | `POST /operations/{op_id}/acknowledge` | Row clears from Needs action | — | `operation.updated` |
| Export trace | `POST /assessments/{id}/trace-exports` | "Preparing…" then download link | — | `export.ready` |
| Replay from ledger (operator tool) | `POST /assessments/{id}/ledger-replays` (only when `worker-replay` runs, `--profile ops`) | Link to the replay run | `409 REPLAY_UNAVAILABLE` → "Some recorded responses are missing for this run" | `run.state_changed` for the replay |
| Cancel run | `POST /assessments/{id}/cancel` `{ confirm: "<assessment_id>" }` after a typed confirmation dialog (admin) | State shows cancelling | `409 ALREADY_TERMINAL` | `run.state_changed` to `CANCELLED` |
| Run reconciliation | `POST /ops/reconciliation/run` | Button shows running | `409 RECONCILIATION_RUNNING` | `reconciliation.completed` |
| Trigger sourcing batch | `POST /ops/sourcing/batches` `{ sources?: [] }` (admin) | New batch row, running | `409` when a batch is running | `sourcing.batch_completed` |
| Save configuration | `POST /config/versions` `{ scope: agents \| budgets \| sources \| review \| retention, base_version_id, changes }` (admin) | Diff, then "Saved as version N" | `422 CONFIG_INVALID` (e.g. model not available on the account); `409 CONFIG_BASE_OUTDATED` | `config.version_created` |
| Export tenant data | `POST /tenant/export` (owner) | "Preparing…" then download link | — | `export.ready` |
| Request deletion | `POST /tenant/delete-requests` `{ scope, confirm }` (owner, typed confirmation) | Request listed with status | `403 FORBIDDEN` | status via `GET /tenant/delete-requests` |
| Change a member's role | `PATCH /tenant/members/{id}` `{ role }` (owner) | Row updates | `409` when removing the last owner | — |
| Pause / resume live tail | client only | — | — | — |

## Real-time event contract

The backend owns the event catalog. It publishes one JSON Schema (2020-12) per event type in `schemas/events/` and serves the bundle at `GET /api/v1/events/schema`; the frontend generates Zod schemas and TypeScript types from it. Events are written to the transactional outbox in the same transaction as the business change, so a UI never hears about something that did not commit.

&#91;embedded content: Event delivery path · 5 steps\]

**Transport.** Server-Sent Events at `GET /api/v1/events/stream?audience=research|console` with the session cookie. Each message carries `id:` (the event ID), `event:` (the type) and `data:` (the envelope). The gateway filters by the caller's tenant and role; console events never reach analysts, and research users receive `system.status_changed` with only `mode`. A comment heartbeat goes out every 15 s. On reconnect the browser sends `Last-Event-ID`; the gateway replays from the log, or sends `event: resync` if the ID is older than 72 hours, and the client then refetches all active queries.

```ts
type ThesisEvent<T extends EventType = EventType> = {
  id: string;              // ULID, increasing per firm; also the SSE id
  type: T;                 // e.g. "assessment.state_changed"
  version: 1;              // bump = new schema file; old version kept for one release
  occurred_at: string;     // ISO 8601 UTC, commit time
  sequence: number;        // strictly increasing per subject; client drops anything older than it has applied
  subject: { kind: SubjectKind; id: string };
  audience: "research" | "console";
  data: EventPayload<T>;
};
```

**Catalog**

| Type | Audience | Payload `data` | Emitted when |
| --- | --- | --- | --- |
| `assessment.created` | research | `assessment_id, company_id, revision, trigger, outcome` | Submission creates or reuses an assessment |
| `assessment.state_changed` | research | `assessment_id, revision, from, to` | Lifecycle transition commits |
| `assessment.progress` | research | `assessment_id, revision, stage, domains_complete, domains_total, documents_ready?, documents_total?` (legacy `questions_answered`, `questions_total` may also be present; ignore them) | Coverage changes during research |
| `assessment.revision_created` | research | `assessment_id, revision, reason` (request\_research, monitoring, reassessment, evidence) | New revision opens |
| `assessment.memo_ready` | research | `assessment_id, memo_version_id` | Memo version stored |
| `review.requested` | research | `assessment_id, target, target_digest, policy` | Assessment enters review |
| `review.decided` | research | `assessment_id, target_digest, decision, reviewer { id, name }` | Update accepted |
| `review.superseded` | research | `assessment_id, old_target_digest, new_target_digest, reason` | New evidence replaces a pending target |
| `monitoring.event_detected` | research | `event_id, company_id, event_type, materiality, action, summary` | Monitoring records a change |
| `watchlist.updated` | research | `entry_id, company_id, paused, rules` | Watch added, changed, paused or resumed |
| `config.version_created` | both | `version_id, number, scope` | Configuration saved |
| `notification.created` | research | `notification_id, title, target_url` | Notification created for this user |
| `system.status_changed` | both | `mode` (research); plus `provider_state, queues[]` (console) | Readiness mode or queue health changes |
| `run.state_changed` | console | `assessment_id, revision, from, to` | Same transition, with system detail |
| `run.stage_started` / `run.stage_completed` | console | `assessment_id, stage, queue, attempt, outcome?, duration_ms?` | Stage boundaries |
| `operation.updated` | console | `operation_id, assessment_id, role, status, attempt_count, cost_usd, cost_certainty` | Ledger row transition |
| `budget.reservation_changed` | console | `reservation_id, operation_id, level, status, amount_usd` | Reserve, settle, release, expire, reclaim |
| `budget.exhausted` / `budget.override_applied` | console | `assessment_id, level, limit_usd, by?` | Limit hit or raised |
| `finding.recorded` | console | `assessment_id, code, where, summary` | Provenance, injection, source-policy or contradiction finding |
| `queue.health_changed` | console | `queue, pollers, backlog` | Pollers or backlog cross a threshold |
| `reconciliation.completed` | console | `run_id, repairs[{ kind, count }]` | Reconciler finishes |
| `outbox.delivery_changed` | console | `outbox_id, target, status, attempt` | Delivery attempt result |
| `export.ready` | console | `export_id, assessment_id, download_url, expires_at` | Trace export finished |
| `quality.report_published` | console | `report_id, corpus_version` | Nightly evaluation stored |

Two further console events complete the catalog: `sourcing.batch_completed` (`batch_id, candidates, eligible, duplicates_merged, dispatched`) when a sourcing batch finishes, and `feedback.recorded` (`feedback_id, assessment_id, memo_version_id, rating, reasons[]`) when a reader rates a memo. system.status\_changed also carries search { provider, state, engines\[\], last\_canary\_at } for console users and search\_state alone for research users. The backend schema bundle is authoritative; if it lists a type this document does not, implement it and flag the omission.

**Client handling**

- Validate every message with its generated Zod schema. Unknown types are ignored and counted; invalid payloads are reported to `POST /api/v1/client-errors` and trigger a refetch of the subject's queries.
- Apply events in `sequence` order per subject; drop duplicates by `id` (delivery is at least once).
- `lib/events/invalidate.ts` maps each type to the TanStack Query keys it updates. Small, self-contained payloads (`assessment.progress`, `operation.updated`) patch the cache; everything else invalidates and refetches.
- The connection state is visible: the Live indicator turns grey with "Reconnecting…" after 5 s without a heartbeat.

## States, copy and accessibility

**Every data region has four states:** loading (skeletons shaped like the content, never spinners on whole pages), empty (one sentence on why plus the next action), error (the mapped copy plus Retry), and live. Pages never blank out on refetch; stale data stays visible with a subtle "Updating" mark.

**Readiness modes** come from `system.status_changed` and `GET /system/status`.

| Mode | Research app | Agent console |
| --- | --- | --- |
| `live_ready` | No banner; sidebar card "All systems normal" | Green status card |
| `setup_required` | Banner "Live diligence is paused until your admin connects OpenAI…", Start diligence disabled with reason; "Explore the demo workspace" if it is seeded | Banner `CREDENTIALS_MISSING` with fix steps; Resume disabled |
| `demo_ready` | Banner "You are in the demo workspace: sample companies stored on this server. Starting new diligence needs OpenAI." | `GET /system/status` → `mode: demo_ready`, `demo_workspace: ready`; costs are the seeded runs' recorded costs, labelled sample |
| `degraded` | Banner "Research is running slower than usual…" | Banner names the queue; Health badge red |

**Search state** is reported separately from the mode. When `search.state` is `degraded` or `unavailable`, the Research app shows "Web search is limited right now, so some news coverage may be missing" and keeps every action enabled. The console names the failed engines and links to Health. No screen ever asks for a search API key, because the default SearXNG needs none.

**Copy.** All investor-facing wording for states and errors lives in `lib/status-copy.ts`, exactly as in the plan's status-translation table, so it can be reviewed and tested in one place. Numbers are always printed next to visuals ("3.8", "21 of 27 confirmed"). Dates are relative within 24 hours, absolute after.

**Roles.** Read roles from `GET /me` and follow the plan's role matrix: analysts and partners use the Research app (partners also decide at or above the advance threshold and edit the thesis); operators use the console's operational pages; admins have both apps plus configuration, cancellation and budget overrides; owners additionally manage members, export and deletion. Hide what a role cannot do, and treat a `403` as a sign the session is stale: refetch `/me` and re-render.

**Accessibility.** WCAG 2.2 AA. Real `<button>` and `<a>` elements; tabs follow the ARIA tabs pattern; the command palette and dialogs trap focus and close on Escape; ⌘K and Ctrl+K open the palette, and no other global shortcuts exist. Charts carry an `aria-label` with the same sentence a sighted reader gets, plus a visually hidden data table. Status is never conveyed by colour alone. Live regions announce toasts politely; the event tail does not announce. Touch targets are at least 40 px.

## Testing, acceptance and reporting

**Contract tests (block merge)**

- `pnpm gen:api && pnpm gen:events && git diff --exit-code` — generated types match the backend's current OpenAPI and event schemas.
- Every event type in the catalog has an example captured from a real run of the backend's integration suite (`schemas/events/examples/*.json`); the frontend parses all of them with the generated Zod schemas, and the backend validates them against the JSON Schema. A type present on one side only fails both pipelines.
- Every row of the action contract has a test asserting method, path, body shape, `Idempotency-Key` header and the UI result for each listed error code.
- `lib/events/invalidate.ts` must cover every catalog type; a unit test enumerates the schema bundle and fails on a missing entry.

**Browser journeys (Playwright, against the real Compose stack with the demo workspace seeded; the journey that starts new diligence also needs the CI OpenAI key)**

1. Diligence: start Level 2 diligence → `assessment.progress` and `domain.status_changed` update Home and the Domains tab → open company → verdict, four measures and finding-kind bar render from the API → click a finding-kind segment and see filtered Sources → Advance → card shows the decision after `review.decided`.
2. Stale review: open Decisions; in a second session upload a new document to the Level 3 demo assessment, which makes the real workflow supersede the review target; click Advance in the first session → "This report changed…" → review the new version → decide.
3. Concurrent reviewer: a second session decides first → the first sees "{name} decided this a moment ago".
4. Setup required: start with no key → banner, disabled Start research, sample workspace works; console shows `CREDENTIALS_MISSING`; add key and restart workers → `system.status_changed` clears the banner without reload; Resume works.
5. Console: open run → Gantt matches `/timeline` spans; cancel with typed confirmation; run reconciliation twice and see zero repairs the second time.
6. Reconnect: drop the SSE connection mid-run → indicator shows Reconnecting → on reconnect, missed events replay and the page matches a fresh load.
7. Roles: an analyst gets 403 on `/console` and never sees console links; no request from the Research app returns console-only fields.

Produce server-side conditions only by real actions: uploads, validations and decisions through the UI or API; `docker compose stop searxng` or `clamav`; Toxiproxy faults on real connections; killing a worker. There are no test hooks, no event-injection endpoints and no backend stubs. Component tests (Vitest) may render components from API responses recorded by the integration suite; they are `unit` and never count toward done.

**Quality checks.** Axe has no serious violations on any page in both themes; Lighthouse accessibility at least 95; layouts hold at 390, 1024 and 1440 px wide; no hard-coded result strings in `app/` or `components/` (lint rule).

**Definition of done for the UI.** All contract tests and the seven journeys pass in CI against `docker compose up --build` with the demo workspace seeded and the live journey run with the CI OpenAI key, from clean volumes, with reports saved as CI artifacts and linked in `implementation-tracker.json`.

**Report back** with: changed files, generated-type diff, commands run with their real output, Playwright and Axe report links, screenshots of each page in both themes, any endpoint or event you needed that the backend does not yet provide, and anything still incomplete. Never state that a test passed unless you ran it and captured the output.

## Due diligence additions

Canonical backend definitions are in the master plan (levels, workflows, report, endpoints, events), the contracts tab (models and error codes) and the domain specification tab. If anything here disagrees with them, they win; flag the difference.

### Rules that shape every new screen

- Never show one combined score. Source reliability, claim confidence, evidence coverage and attractiveness are four separate visual elements with their own labels.
- Every finding shows its class (verified fact, source-supported, calculation, inference, contradictory, missing, unresolved risk) as a text label, not only a colour.
- Private content (findings with `access: deal_team`, documents, financial tables, Level 3 reports) renders only for deal-team members. Others see a neutral "Restricted to the deal team" row, never the content or its counts by domain.
- Numbers come only from `CalculationResult` or cited claims. A `not_computable` result renders as "Not computable" with the missing inputs and a link to the related information request; never a dash or zero.
- Legal, financial and security sections carry the backend's disclaimer text verbatim.
- Restricted or unavailable states use the section status from the backend (`supported`, `incomplete`, `not_applicable`, `unavailable_at_level`) with its reason.

### New and changed screens

| Route | Purpose | Data | Main components |
| --- | --- | --- | --- |
| `/companies/new` and "Start assessment" dialog | Pick a level (1, 2, 3) with a short description of each and its prerequisites. Level 3 is disabled only for no deal team or a role that cannot start it. When no private model route exists (D1), Level 3 stays available and the picker notes: "AI analysis of your documents is off. Parsing, OCR, validation, calculations and sanctions screening still run." | `GET /me`, `GET /workspace/external-ai-policy` (route only, for non-admins) | LevelPicker (radio cards with prerequisites list) |
| Assessment page, header | Level badge, revision, "Upgrade to Level N" button | `GET /assessments/{id}` | LevelBadge, UpgradeButton |
| Assessment › Domains (new tab) | Twelve rows: domain, status, gate result with reason, coverage bar (found vs required), counts of findings, contradictions, risks, open requests | `GET /assessments/{id}/domains` | DomainProgressTable; row click opens DomainDrawer with findings by class and a Retry button for failed/partial domains |
| Assessment › Report (replaces Memo tab) | 21 sections in order with status chips, inline `[finding]` and `[calc]` markers that open the evidence drawer; table of contents with statuses; version selector; export menu | `GET /assessments/{id}/reports`, `GET /reports/{v}?format=json` | ReportView, SectionStatusChip, ExportMenu (Web, PDF, DOCX, JSON) |
| Assessment › Data room (new, Level 3, deal team) | Upload (drag and drop, multi-file), list of documents with status pipeline (uploaded → scanning → parsing → classified → needs validation → ready), reject reasons, classification with override, version history, delete | `GET /assessments/{id}/documents`, `document.status_changed` | Dropzone (client checks size and extension only as a hint; the server decides), DocumentTable, ClassificationSelect |
| Assessment › Financials (new, Level 3, deal team) | Validation queue: each table with failed checks, cell grid highlighting low-confidence cells next to a preview of the source page or sheet; edit a cell with a required reason; Validate button. Metrics table: metric, value, unit, period, formula version, inputs (links), status | `GET /assessments/{id}/financials`, `/financial-tables/{id}`, `/calculations` | ValidationQueue, TableGrid, SourcePreview, MetricTable |
| Assessment › Risks (new) | Risk register: severity, likelihood, domains, linked findings, mitigation question, status, owner; filter and sort; change status or owner | `GET /assessments/{id}/risks` | RiskTable, RiskMatrix (severity × likelihood, counts only) |
| Assessment › Contradictions (extended) | Side-by-side claims with locators (URL or document page/sheet), tolerance, status; add an audited note | `GET /assessments/{id}/contradictions` | ContradictionCompare (existing) with document locators |
| Assessment › Requests (new) | Missing-document requests: item, reason, blocking flag, status; mark sent / received / waived; link an uploaded document; copy all open requests as text for email | `GET /assessments/{id}/information-requests` | RequestList |
| Settings › Workspace | External AI policy (D1; owner or admin with step-up): off by default; enable per provider, data category and purpose with expiry; local model status and probe. Retention (D2): days after closure (0–90, shorten only), legal holds list. Deal-team defaults | `GET`/`PUT /workspace/external-ai-policy`, `POST /workspace/external-ai-policy/local-model/verify`, `GET`/`PUT /workspace/retention`, `GET /workspace/external-transmissions` | ExternalAIPolicyPanel: current route (none / local / external), checklist of categories and purposes, provider terms reference, who authorized and when, expiry; the consent dialog lists exactly what may be sent and requires typing the workspace name. RetentionPanel: days, holds with reason and reference |
| Assessment › Deal team | Add or remove members (partner and above) | `GET`/`PUT /assessments/{id}/deal-team` | MemberPicker |
| Console › Health (extended) | Rows for ClamAV (signature age), worker-docs and Tesseract (version, language packs), embeddings, OFAC datasets (publish date, retrieval time, status), local model probe, retention scheduler (last run, failed deletions), alongside SearXNG and OpenAI | `GET /system/status` | ProviderHealthRow |
| Console › Costs (extended) | Budgets by level and by domain; reserved vs actual vs unknown | `GET /assessments/{id}/budget` | BudgetBullets (existing) grouped by domain |

### Actions

| Action | Request | Errors and copy |
| --- | --- | --- |
| Start at level | `POST /companies { ..., level }` | `403 LEVEL_NOT_ALLOWED` → "Your role can't start enhanced diligence". Level 3 never fails for missing AI consent; skipped model steps are shown on the Domains tab with "AI analysis of private documents is off (workspace setting)" |
| Upgrade | `POST /assessments/{id}/upgrade { level }` | Same as above; success shows the new revision |
| Retry domain | `POST /assessments/{id}/domains/{domain_id}/retry` | `409` if the domain is running |
| Upload | `POST /assessments/{id}/documents` multipart + `Idempotency-Key` | `415 UNSUPPORTED_FORMAT` → "This file type isn't supported"; `422 UPLOAD_REJECTED` → reason from server; `422 MALWARE_DETECTED` → "This file was blocked by the virus scan"; `403 NOT_ON_DEAL_TEAM` |
| Override classification | `POST /documents/{id}/classification { class }` | — |
| Delete document version | `DELETE /documents/{id}/versions/{v}` (confirm in an in-page dialog, not a browser dialog) | Findings citing it show "Source deleted" |
| Correct cell | `POST /financial-tables/{id}/corrections { cell, value, reason }` | Reason required |
| Validate table | `POST /financial-tables/{id}/validate` | `409` if checks still fail and no override reason |
| Update risk | `PATCH /risks/{id} { status?, owner_user_id? }` | — |
| Note on contradiction | `POST /contradictions/{id}/notes { text }` | — |
| Update request | `PATCH /information-requests/{id} { status, linked_document_ids? }` | — |
| Export | `GET /reports/{v}?format=pdf\|docx\|json` | `404 MEMO_NOT_READY` alias → "The report isn't ready yet" |
| Change external AI policy (D1) | `PUT /workspace/external-ai-policy { external_processing_enabled, provider, allowed_categories[], allowed_purposes[], provider_terms_reference, expires_at }` after step-up re-authentication; `403` without step-up → "Confirm your password to change this setting" | Owner only |

### Events

Add these to the catalog and the query-invalidation map, with the payloads defined in the master plan: `domain.status_changed` → Domains tab and header progress; `contradiction.detected` → Contradictions tab count; `document.status_changed` → Data room row (deal team only); `financials.validation_required` and `financials.validated` → Financials tab badge; `risk.updated` → Risks tab; `information_request.updated` → Requests tab; `report.version_created` → Report tab version list (also sent as `assessment.memo_ready` for compatibility; handle either, de-duplicate by version id). Upgrades arrive as `assessment.revision_created` with reason `upgrade`.

### Decisions, settings, stages and waiting

- **Decisions.** Buttons map to `SubmitReviewRequest.decision`: Advance → `approve`, Pass → `reject`, Research more → `request_research`, Request more information → `request_information` with a required list of `requested_items` (an inline list editor, at least one item). After `request_information` the card shows "Waiting for information" and links to the Requests tab.
- **Settings › Diligence domains.** Load with `GET /config/domains`; save the whole list with `PUT /config/domains` (owner or admin). `422 DOMAIN_REQUIRED` → "Thesis fit always runs". On `config.version_created` show "Saved as configuration v{n}. Running assessments keep their version."
- **Stages.** Everywhere a state is shown, show the stage beside it when present (investor copy from `lib/status-copy.ts`, keyed by state + stage, e.g. `RESEARCHING` + `awaiting_validation` → "Waiting for a table to be checked"). The console shows the raw `STATE · stage`. Never invent states.
- **Waiting for validation.** A financials domain in `awaiting_validation` shows how long it has waited and the policy (reminder 24 h, escalation 72 h, closes as partial after 7 days). After `validation_timeout` the domain row reads "Partial · table was not checked in time".

### Demo workspace data

The demo workspace is loaded into PostgreSQL by the backend's `seed-demo` job from the seed set published with the design prototype (`project/fixtures/dd/`: summaries, domains, findings, report, financial tables, calculations, risks, requests, documents, domain config, events), with its documents ingested through the real pipeline. The frontend never reads these files; it reads the same data through the API. Use them only to know what the demo user should see.

### What the demo user sees

Without an OpenAI key the app loads in `demo_ready` (or `setup_required` if the workspace is not seeded). The demo user sees three sample companies, one at each level. The Level 3 company has a data room with a ready deck, a KPI workbook with one table in `needs_validation`, a cap table, a `not_computable` CAC, an ARR contradiction, risks and open requests, so every screen has content. Actions the demo user takes are real writes in `frm_demo`.

### Tests to add

1. Level picker: Level 3 disabled for no deal team and for the analyst role; with no private model route it stays enabled and shows the D1 note.
2. Upgrade L1 → L2: new revision appears, Domains tab shows previously unavailable domains running.
3. Upload: a real EICAR test file shows the blocked message; renamed file shows the server reason; status pipeline advances on `document.status_changed`.
4. Validation: correct a cell with reason, validate, metric changes from "Not computable" or flagged to computed.
5. Access: an analyst outside the deal team sees "Restricted to the deal team" in Data room, Financials and private report sections, and no private counts.
6. Report: 21 headings with statuses; `unavailable_at_level` sections show the reason; export menu downloads PDF, DOCX and JSON.
7. Four measures render separately; no element combines them (DOM assertion).
8. Domain retry after `domain.status_changed` to failed.

These are specified, not run. All of them run against the real stack; report each with its CI run ID. Unit-level component tests are reported separately and do not count toward done.

## Decisions D1–D6 in the UI

Canonical behaviour: plan › Master plan › Approved decisions D1–D6.

| Area | Screen and behaviour | Data and actions | Events |
| --- | --- | --- | --- |
| D1 External AI | Settings panel above; on the Domains and Report tabs, steps skipped for D1 show the reason and, for admins, a link to Settings. Never a toggle that only hides UI: the server decides | `GET`/`PUT /workspace/external-ai-policy`; `GET /workspace/external-transmissions` (admin audit table: time, purpose, categories, counts, no content) | `external_ai_policy.changed` |
| D2 Retention | Data room header shows "Deleted on {date} (90 days after closure)" or "On legal hold". Reopened assessments show the unchanged date and, for admins, "Extend once" with a required reason. A deleted data room shows "Deleted under retention policy on {date}; full erasure from backups by {date}" | `GET /data-rooms/{id}/retention`; `POST /data-rooms/{id}/deletion-requests` (confirm in an in-page dialog); `POST`/`DELETE /data-rooms/{id}/legal-holds/{hold_id}`; `POST /data-rooms/{id}/retention-extension` | `data_room.deletion_scheduled`, `data_room.deleted`, `data_room.deletion_failed`, `legal_hold.changed` |
| D3 Sanctions | Legal domain shows a Screening panel: dataset names, publish date and retrieval time, status (current, older than 3 days, unavailable). Potential matches list subject, matched list name, score band and corroborating attributes. Actions: Dismiss as false positive (reason required), Escalate; Confirm only for `compliance_reviewer`. Copy never says "sanctioned"; it says "Potential match: requires human review", with the disclaimer "Informational diligence aid, not a substitute for professional compliance review." | `GET /assessments/{id}/screening`; `PATCH /potential-matches/{id} { review_status, review_reason }` | `screening.completed`, `potential_match.updated`, `sanctions.dataset_updated`, `sanctions.dataset_failed` |
| D4 OCR | Document rows show pages read by OCR ("12 of 30 pages read by OCR") and low-confidence pages. Evidence locators show an "OCR" badge with confidence. Image uploads (PNG, JPEG, TIFF) are accepted | `DocumentSpan.extraction_method`, `ocr_confidence`, `OcrPageResult[]` on the document version | `document.status_changed` (warnings in `reason`) |
| D5 Licence | About dialog: "Apache-2.0" with links to LICENSE, NOTICE and third-party notices | Static files served by the web app | — |
| D6 | No UI; test infrastructure only | — | — |

**Tests to add.**

1. A non-admin cannot open the consent dialog; an admin must step up, and the dialog lists exactly the categories that will be sent.
2. The retention date is unchanged after reopening; the extend action appears once.
3. A hold blocks the delete button with an explanation.
4. A potential match can be dismissed only with a reason, and the word "sanctioned" never renders (DOM assertion).
5. The OCR badge and confidence render for OCR spans.
6. A stale sanctions dataset shows "unavailable" and never "no matches".

All run against the real stack.
