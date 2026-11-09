# Thesis

Open-source, self-hostable VC due diligence agent. Working UI name: **Thesis**. Licence: Apache-2.0.

Built from the hand-off package in `vc-dd-agent-handoff/` (spec, prototype, fixtures). Work proceeds in nine testable stages so each slice works before the next depends on it.

**Standing order:** continue on this codebase — do not restart. Preserve passing tests. Remediation items live in `docs/remediation-backlog.md` with P0/P1/P2 gates; baseline snapshot in `implementation-baseline.json`. P0 (D1 + tenant isolation) must be satisfied before private-document features. **Not production-ready** until remediation is independently verified.

## Product tour

Agents research a company on the public web at **Level 1 → 2 → 3**; partners decide on a frozen report version. Screenshots below are live demo runs (Notion L1, Figma L2, Candid Health L3).

<p align="center">
  <img src="docs/media/product-tour.gif" alt="Thesis product walkthrough across Level 1, 2, and 3 diligence reports" width="720" />
</p>

### Diligence levels

| Level 1 · Notion | Level 2 · Figma | Level 3 · Candid Health |
| :---: | :---: | :---: |
| <img src="docs/media/02-l1-overview.png" alt="Level 1 Notion — advance suggestion with deepen to Level 2" width="280" /> | <img src="docs/media/04-l2-overview.png" alt="Level 2 Figma — pass suggestion with cleared and open workstreams" width="280" /> | <img src="docs/media/06-l3-overview.png" alt="Level 3 Candid Health — enhanced diligence ready for partner decision" width="280" /> |
| Initial public screen · **5/5** workstreams cleared · deepen in place | Full public diligence · **5 cleared / 6 open gaps** · partner still decides | All 12 domains + data room · risks from live gates · frozen review target |

### Where the value shows up

| Cited findings (L1) | Workstream gates (L2) | Risk register (L3) |
| :---: | :---: | :---: |
| <img src="docs/media/03-l1-findings.png" alt="Level 1 Notion findings with multi-source citations" width="280" /> | <img src="docs/media/05-l2-workstreams.png" alt="Level 2 Figma workstreams — 5 cleared on independent sources" width="280" /> | <img src="docs/media/07-l3-risks.png" alt="Level 3 Candid Health risk register from agent gaps" width="280" /> |
| Multi-source findings partners can verify or contest | Independent-source gates (not claim-row math) | Live risks from insufficient/partial gates |

| Home queue | Partner decisions |
| :---: | :---: |
| <img src="docs/media/01-home.png" alt="Home dashboard with multi-level pending decisions" width="360" /> | <img src="docs/media/08-decisions.png" alt="Decisions queue across assessments" width="360" /> |

Regenerate screenshots + GIF after UI changes (stack must be up on `:3000`, with L1/L2 IDs in `/tmp/l1_id.txt` and `/tmp/l2_id.txt` if you want fresh companies):

```bash
npm install --no-save playwright@1.49.1
node scripts/capture_readme_media.mjs
uv pip install pillow && uv run python scripts/capture_readme_media.py
```

## Architecture

Self-hosted Compose stack: partners use the Research UI; agents run on Temporal; evidence lands in Postgres + SeaweedFS; partners decide on a frozen revision.

<p align="center">
  <img src="docs/media/architecture-flow.jpg" alt="Thesis architecture — partners, Temporal screening spine, L1–L3 levels, data plane, and partner decision loop" width="920" />
</p>

```mermaid
flowchart TB
  subgraph Partners["Partner surfaces"]
    UI["Research app · Next.js :3000"]
    CON["Agent console"]
  end

  API(["API · FastAPI :8001"])
  UI --> API
  CON --> API

  subgraph Spine["Temporal · CompanyScreeningWorkflow"]
    direction LR
    P["1 Plan"] --> R["2 Research"]
    R --> V["3 Validate"]
    V --> E["4 Evaluate"]
    E --> C["5 Critic"]
    C --> M["6 Memo"]
    M --> A["7 Awaiting review"]
  end

  API -->|start / deepen / review| Spine

  subgraph Tools["Research tools"]
    SX[SearXNG]
    SF[SafeFetch]
    LLM["OpenAI · optional"]
  end
  R -.-> SX
  R -.-> SF
  M -.-> LLM

  subgraph Levels["Diligence depth"]
    L1["L1 · Initial public screen<br/>5 domains"]
    L2["L2 · Full public workstreams<br/>11 domains"]
    L3["L3 · Enhanced + data room<br/>12 domains"]
  end
  Spine --- Levels

  subgraph Data["Data plane"]
    PG[("Postgres + pgvector<br/>RLS · claims · reviews")]
    S3[("SeaweedFS S3<br/>artifacts · dataroom")]
    OB["Outbox → notifications"]
  end
  API --> PG
  Spine --> PG
  Spine --> S3
  Spine --> OB

  subgraph Gated["L3 gated · fail-closed"]
    CL[ClamAV]
    OCR["worker-docs OCR · q.docs"]
  end
  L3 -.-> Gated
  OCR --> S3

  subgraph Decide["Partner decides on frozen revision"]
    D1["Advance"]
    D2["Pass"]
    D3["Request info"]
    D4["Ask research"]
  end
  A --> Decide
  Decide -->|decision| API
```

**Flow in one line:** partner starts diligence → API enqueues Temporal screening → worker discovers/fetches public sources → writes claims & memo → partner decides on that revision (private docs stay ClamAV/OCR-gated).

## Stage status

| Stage | Deliverable | Status |
| --- | --- | --- |
| 1 · Contracts | ADRs, schemas, lifecycle, ledger, budgets, FIX-01 | **Tested (unit)** |
| 2 · Runnable shell | Compose, API, UI, Temporal, seed, SearXNG, auth/setup | **Running locally** |
| 3 · Durable execution | Worker `q.system`, ledger tables, budget schema | **Running locally** |
| 4 · Evidence | Claims/contradictions, SafeFetcher, corroboration, `evidence_store` snapshot/span persistence | **Implemented · local E2E** (two-firm DB isolation + FET-06 product pin still open) |
| 5 · Screening | SearXNG/heuristic discover → SafeFetch real pages → claims/corroboration; SonderMind E2E with non-`example.com` sources | **Implemented · local E2E** (OFAC fixture path + D6 ci-local fixture tested; SearXNG often degraded → site heuristics) |
| 6 · Human review | Review API, deal-team, data-room create/list scaffold, ddcalc queue | **Partial** — ClamAV/worker-docs/OCR upload still gated |
| 7 · Delivery | Outbox → notifications, optional webhook, `OutboxDispatchWorkflow` | **Implemented · local** (SMTP not shipped) |
| 8 · Hardening | RLS + `SET ROLE thesis_app`, retention dry-run `DeletionCertificate` | **Partial** — destructive object delete still gated |
| 9 · OSS release | Apache-2.0 LICENSE, NOTICE, SPDX seed + licence gate CI | **In progress** — full dep/image pin audit still open (REM-P1-06) |

**UI:** Research app shell (Home, Companies, Start assessment, Assessment tabs, Decisions, Watchlist, Thesis) and Agent console (Runs, Health, Reconciliation) now follow `docs/thesis-ui.md` tokens and IA. Still missing vs design: TanStack Query + OpenAPI codegen, full shadcn component kit, Gantt/timeline, PDF export, settings D1/D2 panels, Playwright journeys.

## Quick start

```bash
cp .env.example .env          # leave OPENAI_API_KEY empty
docker compose up --build -d
# UI:  http://localhost:3000
# API: http://localhost:8001  (mapped to container :8000; change compose if 8000 is free)
```

Contract tests (Stage 1):

```bash
uv sync
uv run pytest -q
```

Canonical contracts: `packages/contracts`. Spec: `docs/`. Seed fixtures: `fixtures/dd` (`frm_dev` → `frm_demo` at seed; errata E4). Object store default is SeaweedFS (ADR-017; confirm B1).

## Rules that stay in force

See `vc-dd-agent-handoff/README_FOR_AGENT.md`. Real integrations only (no MSW / `DEMO_MODE`). UI must load without an OpenAI key. D6 stays blocked until the fixture site is deployed.
