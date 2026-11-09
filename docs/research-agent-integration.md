# Research-agent pattern integration (ongoing)

**Directive date:** 2026-11-08  
**Rule:** Do not restart Thesis. Adapt patterns into Temporal + eight agents + twelve domains. Preserve remediation backlog.

## Current Thesis baseline (before this directive)

| Area | Status |
| --- | --- |
| Contracts / lifecycle / ledger / DD models | Implemented · unit tested (24) |
| Compose shell, SearXNG canary, seed demo | Running |
| Auth /setup / sessions | Implemented |
| Temporal worker `q.system` | Scaffold |
| Entity resolution runtime | Missing (identity types only) |
| Evidence lineage enforcement | Partial (EvidenceSpan/Finding contracts; no runtime chain check) |
| Contradiction preservation | Partial (`Finding.kind=contradictory`; no Contradiction store/API) |
| Sufficiency gates | Specified in domain docs; not enforced in code |
| VoI research planning | Missing |
| SearXNG cache/normalize/degrade | Health canary only |
| Real-time research progress UI | Durable SSE + ProgressPanel (Stage 5) |
| Research eval harness | Fixture harness + baseline (`baselines/research_eval_baseline.json`); live D6 blocked |

## Reference audit (code-level)

| Repo | Licence | Maintenance signal | Useful patterns | Do not take |
| --- | --- | --- | --- | --- |
| [hass44/ai-hackathon](https://github.com/hass44/ai-hackathon) (FirstSignal) | **No LICENSE file** — ideas only, no code copy | Active hackathon monorepo; contracts + gold fixtures | Persistent founder/company entities; Claim↔EvidenceSpan; Contradiction with trust_state; VoI `DiligenceAction`; abstain on insufficient evidence | Any source files; LangGraph if present |
| [assafelovic/gpt-researcher](https://github.com/assafelovic/gpt-researcher) | **Apache-2.0** | Large, active | Sub-query planning, bounded deep research, context select/compress, retriever plugin surface, citation/visited URL tracking | LangGraph as orchestrator; default paid Tavily as mandatory |
| [Intelligent-Internet/ii-researcher](https://github.com/Intelligent-Internet/ii-researcher) | **Apache-2.0** | Active | `BaseTool` ABC + `execute_stream`; `StreamManager` event types; provider-swappable search client | Mandatory Tavily/SerpAPI; replacing Temporal |
| [cedarsaam/agent-search](https://github.com/cedarsaam/agent-search) | **MIT** | Active; strong unit tests | SearXNG cache keys, URL clean/normalize, result merge/dedup, SSRF-safe fetch, failure counting / empty-result expand | FlareSolverr CAPTCHA bypass; stealth scraping |

## Gap map → Thesis schedule

| Improvement | Priority | Already | Integrate when |
| --- | --- | --- | --- |
| Company/founder identity resolution + ambiguity review | P0 | Types stub | Now → Stage 4/5 |
| Evidence lineage (claim→span→snapshot) | P0 | `evidence_store` + claim insert in screening | Stage 4 wired · FET-06 product pin open |
| Contradiction tracking (preserve, not silent merge) | P0 | Finding kind only | **Implemented** store/API + Temporal activity; resolution version-checked |
| Evidence sufficiency before invest conclusions | P0 | GateResult enum | Library + progress fields; full domain wiring ongoing |
| Workspace isolation / D1 / human review | P0 | Scaffold + policy | Ongoing (remediation REM-P0-*) |
| Adaptive / VoI planning | P1 | — | Stage 5 Planner |
| Bounded research loops | P1 | Budget contracts | Stage 3–5 |
| Source rank / dedup / corroboration | P1 | — | **Implemented** `corroboration.py` + SafeFetcher activity |
| Context management with citations | P1 | — | Stage 5 Research/Memo (partial lineage) |
| SearXNG cache/throttle/degrade | P1 | Canary | Adapter present → Stage 4 |
| Real-time domain progress UI | P1 | Home status | **Implemented** durable events + SSE + UI |
| Research eval harness | P1 | Spec harnesses only | **Implemented** fixture mode; live blocked on D6 |
| Existing remediation B1–B5, D6, errata | — | Tracked | Unchanged gates |

## Attribution

Patterns adapted (not vendored wholesale). Compatible licences noted above. FirstSignal: **ideas only** (no licence). Add NOTICE entries when Apache/MIT-derived snippets are inlined beyond clean-room reimplementation.
