# Due diligence domain specification

This tab is the canonical source for the twelve diligence domains: what each one needs, where it looks, what it extracts, how it is verified and what it produces. The master plan owns the workflows, gates and report; the contracts tab owns the shared models (`Finding`, `CalculationResult`, `DomainPlan`, `DomainAssessment`, `RiskItem`, `InformationRequest`). Nothing here has been implemented or tested; every test named below is specified only.

## Shared domain contract

Every domain is a `DomainModule`: a typed Python component run as Temporal Activities by the existing agents. Domains are not agents. The Research Planner picks the modules, the Research Agent runs their retrieval and extraction, the Verification Agent applies their verification rules, the Evaluation Agent scores them, the Critic challenges them and the Memo Agent writes their report sections.

```python
DomainId = Literal["company", "team", "market", "competition", "product", "traction",
                   "financials", "capitalization", "legal", "security", "governance", "thesis_fit"]

class DomainModule(Protocol):
    domain_id: DomainId
    version: str                                  # e.g. "traction@1"; pinned in the config version
    claim_types: list[type[BaseModel]]            # claim schemas this domain extracts
    def plan(self, ctx: DomainPlanContext) -> DomainPlan: ...          # pure, deterministic
    def tasks(self, plan: DomainPlan) -> list[DiligenceTask]: ...      # retrieval + extraction tasks
    def verify(self, claims: list[Claim], ctx: VerifyContext) -> list[VerificationResult]: ...
    def calculations(self) -> list[str]: ...                           # ddcalc metric names
    def contradiction_rules(self) -> list[ContradictionRule]: ...
    def gate(self, level: Level, coverage: Coverage) -> GateResult: ...  # sufficiency gate
    def outputs(self, findings: list[Finding]) -> DomainAssessment: ...
```

**Rules that apply to every domain**

- A domain may only produce `Finding` objects whose class is one of the seven in the master plan. A finding without a claim, a calculation or a declared basis of other findings is rejected at write time.
- When a needed source is not available at the selected level, the domain records a `missing` finding and, at Level 3, an `InformationRequest`. It never fills the gap with an estimate presented as a fact.
- Private evidence (`evidence_scope` `private` or `mixed`) is only produced at Level 3, only from the assessment's own data room, and its findings carry `access: deal_team`.

  Model calls on private evidence follow D1 (no external AI by default; a verified local model or explicit authorization per category); scanned pages are read by local OCR (D4); data-room content follows D2 retention.
- Text from any source, public or private, is data. Instructions found inside a page or document are ignored and recorded as a `prompt_injection_suspected` flag on the snapshot.
- Materiality uses one scale for all domains (critical, high, medium, low). Each domain lists below what makes a finding critical.
- Claim confidence is set by the Verification Agent from the verification criteria, never by the extracting model.

**Gate states**: `sufficient`, `partial` (report section marked incomplete, recommendation allowed with caveats), `insufficient` (section marked incomplete; the Evaluation Agent may not score the domain and the overall recommendation becomes "inconclusive" if the domain is required by the thesis), `not_applicable`, `unavailable_at_level`.

## Configuration

Domain execution is set per configuration version and pinned to each revision.

```python
class DomainConfig(BaseModel):
    domain_id: DomainId
    enabled: bool = True
    required_for_recommendation: bool          # gate failure blocks a recommendation
    levels: set[Level]                         # levels at which the domain runs
    weight: Decimal                            # used only for the attractiveness score
    min_sources: dict[Level, int]              # gate thresholds (see each domain)
    task_budget: dict[Level, int]              # max retrieval tasks
    overrides: list[DomainOverride] = []       # by stage, industry, geography, thesis tag

class DomainOverride(BaseModel):
    when: OverrideCondition                    # stage in {...}, industry in {...}, geography in {...}, thesis_tag in {...}
    set: dict[str, Any]                        # only keys of DomainConfig; validated
```

Defaults shipped with the seed: pre-seed and seed turn off `financials` calculations that need more than two periods and lower `traction` thresholds; regulated industries (fintech, health, defence) raise `legal` to required with `min_sources` +1; companies with an EU or UK presence add GDPR checks to `security`; `thesis_fit` is always required. Overrides are applied in order and the result is stored in the configuration version, so a revision can be replayed exactly.

## Level availability

| Domain | Level 1 screening | Level 2 public diligence | Level 3 enhanced |
| --- | --- | --- | --- |
| Company and business model | Runs | Runs | Runs, plus data room |
| Founders, leadership and team | Runs (named founders) | Runs | Runs, plus references supplied by the company |
| Market size and dynamics | Light (one sizing source) | Runs | Runs, plus company market model |
| Competition and differentiation | Light | Runs | Runs, plus win/loss data |
| Product and technology | Light | Runs | Runs, plus architecture documents |
| Traction, customers and GTM | Public signals only | Runs | Runs, plus customer and pipeline data |
| Financial performance, unit economics, runway | Unavailable | Public filings only | Runs with ddcalc |
| Fundraising, capitalization, ownership | Public rounds only | Runs | Runs, plus cap table |
| Legal, IP and regulatory | Unavailable | Public records | Runs, plus contracts and corporate documents |
| Security, privacy and resilience | Unavailable | Public posture | Runs, plus policies, audits, incident log |
| Governance and execution risks | Unavailable | Runs | Runs, plus board materials |
| Thesis fit and return potential | Runs | Runs | Runs with scenarios |

## 1. Company and business model

| Item | Specification |
| --- | --- |
| Required inputs | Company name and primary domain; optional registry number and country |
| Public sources | Company website, registry filings (Companies House, SEC EDGAR, state registries where an open API exists), press releases, app store listings |
| Private sources | Pitch deck, business plan, incorporation documents |
| Tools | `web_search` (SearXNG), `fetch_page` (SafeFetcher + selectolax/trafilatura), `render_page` (Playwright, only if static fetch is empty), `filings_read`, `document_lookup` |
| Claim schemas | `CompanyIdentity{legal_name, jurisdiction, incorporation_date, hq, registry_id}`, `BusinessModel{customer_type, revenue_model, pricing_model, delivery_model}`, `OfferingClaim{product, segment}` |
| Verification | Identity verified only against a registry record or filing; website-only identity is `source_supported`. Business model needs two independent sources or the company's own document plus one public source |
| Calculations | None |
| Contradictions | Legal name or jurisdiction differs between registry and deck; revenue model in deck differs from public pricing page |
| Critical when | Entity cannot be identified, or the entity raising differs from the operating entity without explanation |
| Missing evidence | Identity not found in any registry: `missing` finding and, at Level 3, a request for the certificate of incorporation |
| Outputs | Report sections 2 and 4; company profile fields |
| Gate | L1: website + one other source; L2: registry or filing; L3: plus incorporation documents |
| Tests | Fixture company with matching registry record (verified); fixture with mismatched legal name (contradiction raised); company with no registry match (`missing`, no invented identity) |

## 2. Founders, leadership and team

| Item | Specification |
| --- | --- |
| Required inputs | Founder names from the company site, deck or user input |
| Public sources | Company team page, conference talks, published papers, GitHub profiles (REST API), news, prior company registry records |
| Private sources | Founder CVs, org chart, reference contacts supplied by the company, employment agreements |
| Tools | `web_search`, `fetch_page`, `github_profile`, `filings_read`, `document_lookup` |
| Claim schemas | `PersonRole{person, company, title, start, end}`, `PriorVenture{person, company, outcome}`, `Credential{person, kind, issuer, year}`, `TeamComposition{function, headcount, as_of}` |
| Verification | Roles verified by a source not controlled by the person (employer site, filing, reputable press). Self-published profiles alone are `source_supported`. Social network scraping is excluded |
| Calculations | Team tenure overlap (deterministic, from dated roles) |
| Contradictions | Dates or titles conflict across sources; claimed exit not reflected in acquirer or registry records |
| Critical when | A material credential or prior exit is contradicted; a founder named in the deck does not appear in corporate documents |
| Missing evidence | Only self-reported history: finding stays `source_supported` with a follow-up question. No inference about personal characteristics, protected attributes or private life |
| Outputs | Section 5; founder timeline |
| Gate | L1: each founder has at least one source; L2: at least one independent source per founder; L3: plus CVs or employment agreements for key hires |
| Tests | Founder with consistent dated roles; founder with fabricated exit in fixture deck (contradiction); query must not produce protected-attribute statements (red-team test) |

## 3. Market size and market dynamics

| Item | Specification |
| --- | --- |
| Required inputs | Segment definition from Domain 1 and the thesis |
| Public sources | Government statistics, public company filings in the segment, industry associations, reputable research summaries that are publicly accessible |
| Private sources | Company market model and bottom-up sizing in the deck |
| Tools | `web_search`, `fetch_page`, `filings_read`, `document_lookup`, `ddcalc` |
| Claim schemas | `MarketSizeClaim{segment, geography, metric: TAM\|SAM\|SOM, value, currency, year, method: top_down\|bottom_up, source_id}`, `GrowthClaim{segment, cagr, period}`, `MarketTrend{statement}` |
| Verification | Each size claim keeps its own source and method; claims of different definitions are never averaged. A figure behind a paywall is not retrieved; only its public summary counts |
| Calculations | Bottom-up check: customers × price × penetration, using only cited inputs; CAGR from two cited points |
| Contradictions | Company TAM exceeds every independent estimate by more than a configured factor (default 3×); definitions differ |
| Critical when | Market thesis depends on a size that no independent source supports |
| Missing evidence | No independent sizing: section reports the company's figure as `source_supported` and says no independent estimate was found |
| Outputs | Section 6; a range table of cited estimates, never a single blended number |
| Gate | L1: one sizing source; L2: two independent sources; L3: plus company bottom-up model reconciled |
| Tests | Two sources with different definitions are shown side by side; inflated deck TAM raises contradiction; no estimate available yields `missing` |

## 4. Competition and differentiation

| Item | Specification |
| --- | --- |
| Required inputs | Segment and product description |
| Public sources | Competitor websites and pricing pages, funding announcements, review platforms' public pages, GitHub activity for open-source competitors |
| Private sources | Company competitor analysis, win/loss data |
| Tools | `web_search`, `fetch_page`, `github_repo`, `document_lookup` |
| Claim schemas | `Competitor{name, domain, segment_overlap}`, `FeatureComparison{company, competitor, feature, supported}`, `PricingPoint{company, plan, price, currency, as_of}`, `DifferentiationClaim{statement}` |
| Verification | Feature and pricing claims verified from the competitor's own current page with a snapshot; company claims of superiority are `source_supported` unless a third party supports them |
| Calculations | Win rate from win/loss data (Level 3 only) |
| Contradictions | Deck says "no competitors" while discovery finds companies with overlapping segments; pricing differs from published page |
| Critical when | A well-funded competitor offers the same product and the deck does not mention it |
| Missing evidence | Competitor pricing not public: recorded as unknown, never estimated |
| Outputs | Section 7; competitor table with snapshot dates |
| Gate | L1: three candidate competitors; L2: five with at least two verified feature comparisons; L3: plus win/loss reconciled |
| Tests | Omitted competitor detected; stale pricing page snapshot flagged with its date |

## 5. Product and technology

| Item | Specification |
| --- | --- |
| Required inputs | Product URLs, repositories if any |
| Public sources | Product documentation, changelogs, status pages, public repositories, patents (public patent office search pages), app store listings |
| Private sources | Architecture documents, roadmap, technical due diligence questionnaires |
| Tools | `fetch_page`, `render_page`, `github_repo` (commits, contributors, licences, releases), `document_lookup` |
| Claim schemas | `ProductCapability{feature, status: live\|beta\|planned}`, `TechStackClaim{component}`, `RepoActivity{repo, commits_90d, contributors_90d, last_release}`, `LicenceClaim{repo, spdx}`, `PatentClaim{number, title, assignee, status}` |
| Verification | "Live" requires public documentation, a product page or a working public endpoint; roadmap items are never reported as live. Repository metrics come from the API, not from README badges |
| Calculations | Repository activity trends (deterministic from API counts) |
| Contradictions | Deck shows a feature as live that documentation lists as planned; repository licence conflicts with the claimed commercial model |
| Critical when | Core product depends on code under a licence incompatible with the business model, or the core product is not live while the deck says it is |
| Missing evidence | Closed-source product with no public documentation: findings limited to `source_supported` |
| Outputs | Section 8 |
| Gate | L1: product page; L2: documentation or repository; L3: plus architecture document |
| Tests | Roadmap-vs-live contradiction; GPL dependency flagged in fixture repository; GitHub rate limit returns a typed `RATE_LIMITED` error and retries after reset |

## 6. Traction, customers and go-to-market

| Item | Specification |
| --- | --- |
| Required inputs | Company identity |
| Public sources | Customer logos and case studies on the site, customer press releases, public job postings, app store rankings and review counts |
| Private sources | Customer list, contracts summary, pipeline export, cohort data, sales-team metrics |
| Tools | `web_search`, `fetch_page`, `rss_read`, `document_lookup`, `ddcalc` |
| Claim schemas | `CustomerClaim{customer, relationship: logo\|case_study\|contract, since}`, `TractionMetric{metric, value, unit, period, source_id}`, `GTMClaim{channel, motion}` |
| Verification | A customer relationship is verified only if the customer itself confirms it publicly or a contract is in the data room. Logos alone are `source_supported`. Customer contacts are never approached by the system |
| Calculations | Customer concentration, HHI, NRR, GRR, cohort retention (Level 3, ddcalc) |
| Contradictions | Customer count in deck differs from customer list; claimed logo absent from customer's own site and press; pipeline totals differ from summary |
| Critical when | Top customer cannot be confirmed, or one customer exceeds the configured concentration threshold (default 30% of revenue) |
| Missing evidence | No customer data at Level 3: `InformationRequest` for customer list and revenue by customer; no customer names are invented |
| Outputs | Section 9; concentration chart (Level 3) |
| Gate | L1: public signals listed; L2: at least two verified customers; L3: customer list reconciled to revenue |
| Tests | Logo with no confirmation stays `source_supported`; customer-list vs revenue mismatch raises contradiction; concentration threshold triggers a risk |

## 7. Financial performance, unit economics and runway

| Item | Specification |
| --- | --- |
| Required inputs | Level 3: validated financial tables (income statement, balance sheet or cash, KPIs). Level 2: public filings only |
| Public sources | Regulatory filings (SEC EDGAR financial data), public statutory accounts where a registry publishes them |
| Private sources | Management accounts, audited statements, KPI workbook, budget and forecast, bank statements summary |
| Tools | `filings_read`, `document_lookup`, `table_extract` (pdfplumber, openpyxl, csv), `ddcalc` |
| Claim schemas | `FinancialLineItem{statement, line, period, value, currency, basis: actual\|budget\|forecast, audited: bool, source_ref}`, `KPIValue{metric, period, value, unit, definition_text, source_ref}` |
| Verification | A figure is `verified_fact` only if it appears in audited statements or reconciles across two private sources; otherwise `source_supported`. Values the LLM extracted are proposals until the table passes validation or a deal-team member confirms it in the validation queue |
| Calculations | All metrics in the master plan's financial analysis section: growth, gross margin, gross and net burn, runway, MRR/ARR reconciliation, NRR, GRR, CAC, LTV, payback, forecast vs actual |
| Contradictions | ARR in deck ≠ 12 × MRR from the KPI workbook beyond tolerance (default 2%); totals do not foot; cash in balance sheet ≠ bank summary; forecast for a closed period differs from actuals |
| Critical when | Runway under the configured threshold (default 12 months), or any headline metric in the deck cannot be reconciled |
| Missing evidence | Input missing: `CalculationResult.status = not_computable` with `missing_inputs`; the report shows "not computable" and lists the document request. No estimate replaces a reported figure |
| Outputs | Section 10; metric table with formula version and input links |
| Gate | L2: filings where they exist, otherwise `unavailable_at_level`; L3: at least 12 months of validated monthly actuals for burn and runway, 2 periods for growth |
| Tests | Golden fixtures for every formula; non-footing table blocks calculation; deck/workbook ARR mismatch raises contradiction; missing CAC inputs give `not_computable` and no value |

## 8. Fundraising, capitalization and ownership

| Item | Specification |
| --- | --- |
| Required inputs | Company identity; Level 3 cap table |
| Public sources | Funding announcements, Form D filings (EDGAR), registry share filings, investor portfolio pages |
| Private sources | Cap table, SAFEs and convertible notes, term sheets, shareholder agreements, option plan |
| Tools | `web_search`, `filings_read`, `document_lookup`, `table_extract`, `ddcalc` |
| Claim schemas | `RoundClaim{round, date, amount, currency, lead, investors, source_id}`, `Holding{holder, class, shares, fully_diluted: bool}`, `Instrument{type, principal, cap, discount, interest, maturity}`, `PoolClaim{size, granted, available}` |
| Verification | Round amounts verified by a filing or two independent reputable sources. Cap table totals must equal issued shares in corporate documents |
| Calculations | Fully diluted ownership, conversion of SAFEs and notes under stated terms, pro-forma dilution for a proposed round, option pool shuffle; all with `Decimal` and documented rounding |
| Contradictions | Announced amount differs from filing; cap table total differs from registry; investors named in the press missing from the cap table |
| Critical when | Cap table does not reconcile, or instruments exist whose conversion would materially change ownership and they are absent from the summary |
| Missing evidence | No cap table: ownership scenarios `not_computable`; request issued |
| Outputs | Section 11; ownership and dilution table |
| Gate | L1: public rounds listed; L2: filings checked; L3: cap table reconciled to corporate documents |
| Tests | SAFE conversion golden cases (post-money cap, discount, MFN); cap table off by one share flagged; press/filing mismatch raised |

## 9. Legal, IP and regulatory exposure

| Item | Specification |
| --- | --- |
| Required inputs | Entity identity, jurisdictions, industry |
| Public sources | Court records where publicly searchable without login, regulator enforcement databases, patent and trademark office pages, official OFAC SDN and consolidated datasets (D3), registry filings |
| Private sources | Charter and bylaws, IP assignment agreements, material contracts, licences and permits, litigation summaries |
| Tools | `web_search`, `fetch_page`, `filings_read`, `sanctions_check` (D3: versioned OFAC datasets; returns potential matches for human review), `document_lookup`, `checklist_review` |
| Claim schemas | `LegalChecklistItem{checklist_id, item_id, status: ok\|issue\|missing\|not_applicable, evidence_refs, note}`, `LitigationClaim{case, court, parties, status}`, `RegulatoryClaim{regime, obligation, status}`, `IPAssignment{person, assignee, signed}` |
| Verification | Each checklist item needs a cited document passage or public record. The agent reports issues and questions only; it never states that something is legally compliant |
| Calculations | None |
| Contradictions | IP created by founders before incorporation with no assignment; contract change-of-control clause vs deck claims of transferability |
| Critical when | Missing IP assignment for core technology, active material litigation, a sanctions match confirmed by compliance or a strong potential match still pending review, operating without a required licence |
| Missing evidence | Item without evidence stays `missing` and becomes a request; never `ok` by default |
| Outputs | Section 12; legal checklist with statuses; mandatory disclaimer that this is not legal advice |
| Gate | L2: public records searched for each jurisdiction; L3: all required checklist items have status other than `missing` or have a request open |
| Tests | Synthetic OFAC-format list: a strong potential match goes to review and is never reported as "sanctioned"; stale dataset reported as unavailable; missing assignment detected; output contains no compliance certification wording (lint test) |

## 10. Security, privacy and operational resilience

| Item | Specification |
| --- | --- |
| Required inputs | Primary domain, product URLs |
| Public sources | Security and trust pages, privacy policy, published certifications (SOC 2 or ISO 27001 claims), public breach disclosures and regulator notices, DNS and TLS configuration observable without intrusion, status page history |
| Private sources | Security policies, penetration test summaries, SOC 2 report, incident log, subprocessor list, DPA, business continuity plan |
| Tools | `fetch_page`, `dns_tls_check` (passive: DNS records, TLS certificate and protocol, security headers on public pages), `web_search`, `document_lookup`, `checklist_review` |
| Claim schemas | `SecurityControlClaim{control, status, evidence_ref}`, `CertificationClaim{standard, scope, period, auditor}`, `IncidentClaim{date, nature, disclosed}`, `Subprocessor{name, purpose, region}` |
| Verification | Certification claims verified only by the report or the auditor's public registry; trust-page badges alone are `source_supported`. No scanning beyond a normal page load and DNS/TLS lookups; no vulnerability probing |
| Calculations | Days since last pen test; certification validity window |
| Contradictions | Privacy policy lists regions that conflict with subprocessor list; claimed certification out of date |
| Critical when | Undisclosed incident, expired or unsupported certification claim, personal data processed without a stated lawful basis where GDPR applies |
| Missing evidence | Item without evidence stays `missing`; requests created at Level 3 |
| Outputs | Section 13; security checklist; disclaimer that this is not a security certification |
| Gate | L2: public posture checked; L3: policy set and latest audit or pen test summary reviewed |
| Tests | Passive check never sends requests beyond allowed endpoints (egress test); expired certificate flagged; badge-only SOC 2 stays `source_supported` |

## 11. Governance and execution risks

| Item | Specification |
| --- | --- |
| Required inputs | Findings from Domains 2, 6, 7, 8 |
| Public sources | Board composition announcements, executive departures in news, job posting trends |
| Private sources | Board minutes, board decks, investor updates, hiring plan |
| Tools | `web_search`, `rss_read`, `document_lookup` |
| Claim schemas | `BoardSeat{person, role, appointed_by}`, `ExecutionMilestone{milestone, planned_date, actual_date}`, `KeyPersonDependency{person, function}` |
| Verification | Milestones verified against dated documents; departures verified by two sources |
| Calculations | Milestone slippage (days), forecast vs actual from Domain 7 |
| Contradictions | Investor updates claim milestones that board minutes show missed |
| Critical when | Key-person dependency without succession, repeated missed milestones, related-party transactions |
| Missing evidence | Recorded as `missing`; no assumptions about board conduct |
| Outputs | Feeds section 14 (red flags) and 20 (IC considerations) |
| Gate | L2: public signals; L3: board materials for the last four quarters where they exist |
| Tests | Slippage computed from dated fixtures; related-party flag from fixture minutes |

## 12. Investment-thesis fit and return potential

| Item | Specification |
| --- | --- |
| Required inputs | Pinned thesis version; outputs of all other enabled domains |
| Public sources | None directly; uses other domains' findings and public comparable exits |
| Private sources | Proposed round terms (Level 3) |
| Tools | `ddcalc` (scenarios), Evaluation Agent rubric |
| Claim schemas | `ThesisCriterionResult{criterion_id, met: yes\|no\|partial\|unknown, finding_ids}`, `Scenario{name, assumptions: list[Assumption], exit_value, ownership_at_exit, multiple}` |
| Verification | Each criterion result cites findings; `unknown` when the cited domain's gate is insufficient. Scenario assumptions are labelled `inference` with their basis |
| Calculations | Ownership at exit after modelled dilution, gross multiple, scenario table (bear, base, bull) using only cited or user-entered assumptions |
| Contradictions | Thesis requires a metric the company reports differently from how the thesis defines it |
| Critical when | A hard thesis exclusion is met |
| Missing evidence | Criteria depending on unavailable domains are `unknown`, and the recommendation is "inconclusive" if any required criterion is unknown |
| Outputs | Sections 1, 3 and 18; attractiveness score kept separate from confidence and coverage |
| Gate | Always runs; sufficient when every required criterion is not `unknown` |
| Tests | Hard exclusion forces "pass"; unknown required criterion forces "inconclusive"; scenario with user assumption labelled as such |

## Cross-domain contradiction analysis

After all domain children finish, the Verification Agent runs a deterministic pass over every claim pair that shares a `subject_key` (entity, metric, period). Numeric claims conflict when they differ by more than the metric's tolerance; categorical claims conflict when values differ. Each conflict becomes a `Contradiction{contradiction_id, claim_ids, domain_ids, kind, tolerance, status: open | explained | resolved}`. The Critic then reviews open contradictions and may request bounded follow-up research (at most one round per domain per revision, inside the revision budget). Contradictions are never auto-resolved by picking the more favourable value.
