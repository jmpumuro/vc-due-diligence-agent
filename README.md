# Thesis

Open-source, self-hostable **VC due diligence agent**. Licence: Apache-2.0.

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

## Architecture

Self-hosted Compose stack: partners use the Research UI; agents run on Temporal; evidence lands in Postgres + SeaweedFS; partners decide on a frozen revision.

<p align="center">
  <img src="docs/media/architecture-flow.jpg" alt="Thesis architecture — partners, Temporal screening spine, L1–L3 levels, data plane, and partner decision loop" width="920" />
</p>

```mermaid
flowchart LR
  UI[Research app] --> API[FastAPI]
  CON[Agent console] --> API
  API --> T[Temporal screening]
  T --> P[Plan]
  P --> R[Research]
  R --> V[Validate]
  V --> E[Evaluate]
  E --> C[Critic]
  C --> M[Memo]
  M --> A[Awaiting review]
  R -.-> SX[SearXNG]
  R -.-> SF[SafeFetch]
  A --> D[Partner decision]
  D --> API
```

**Flow:** partner starts diligence → API enqueues Temporal screening → worker discovers/fetches public sources → writes claims & memo → partner decides on that revision (private docs stay ClamAV/OCR-gated).

## Quick start

```bash
cp .env.example .env          # leave OPENAI_API_KEY empty
docker compose up --build -d
# UI:  http://localhost:3000
# API: http://localhost:8001
```

```bash
uv sync --all-packages
uv run pytest -q
```

## Docs

| Doc | What it is |
| --- | --- |
| [`docs/domain-specification.md`](docs/domain-specification.md) | Twelve diligence domains and gates |
| [`docs/remediation-backlog.md`](docs/remediation-backlog.md) | Open P0/P1/P2 gates (not production-ready until cleared) |
| [`docs/adr/`](docs/adr/) | Architecture decisions |
| [`VERIFICATION.md`](VERIFICATION.md) | Acceptance checks |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) / [`SECURITY.md`](SECURITY.md) | Contribute & report issues |
| [`packages/contracts`](packages/contracts) | Typed contracts (source of truth) |

Historical hand-off fixtures/prototypes live under `vc-dd-agent-handoff/` (see its README).

## Rules that stay in force

- Real integrations only (no MSW / fake `DEMO_MODE` network stubs)
- UI must load without an OpenAI key
- Never invent a D6 false-claims site URL
- Do not mark production-ready until Gate H / `VERIFICATION.md` passes
