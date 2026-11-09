import type { ReactNode } from "react";
import Link from "next/link";
import ClaimsSourcesPanel from "@/components/diligence/ClaimsSourcesPanel";
import DomainTable from "@/components/diligence/DomainTable";
import MeasuresRow from "@/components/diligence/MeasuresRow";
import ResearchBrief from "@/components/diligence/ResearchBrief";
import RestartScreenButton from "@/components/diligence/RestartScreenButton";
import VerdictStrip from "@/components/diligence/VerdictStrip";
import ResearchShell from "@/components/shell/ResearchShell";
import { apiJson, publicApiBase } from "@/lib/api";
import { initials, normalizeLikelihood, researchModeColor } from "@/lib/format";
import { sessionCookie } from "@/lib/session";
import {
  agentModeDetail,
  agentModeLabel,
  agentSignalTag,
  levelLabel,
  recBlurb,
  recLabel,
  stateLabel,
  tabCopy,
} from "@/lib/status-copy";
import DataRoomUpload from "@/components/diligence/DataRoomUpload";
import DeepenLevelButton from "@/components/diligence/DeepenLevelButton";
import FindingKindBar from "@/components/diligence/FindingKindBar";
import SanctionsCard from "@/components/diligence/SanctionsCard";
import StatusPill from "@/components/ui/StatusPill";
import ContradictionResolvePanel from "./ContradictionResolvePanel";
import DecideChrome from "./DecideChrome";
import ProgressPanel from "./ProgressPanel";
import ReviewPanel from "./ReviewPanel";

const TABS = [
  "overview",
  "domains",
  "report",
  "contradictions",
  "risks",
  "requests",
  "dataroom",
  "financials",
  "sources",
  "history",
] as const;

type Risk = {
  id: string;
  severity: string;
  likelihood?: string;
  title: string;
  detail: string;
  domain_id?: string;
  claim_ids?: string[];
  finding_excerpt?: string | null;
  source_hosts?: string[];
  gate_result?: string;
  source?: string;
};

type InfoRequest = {
  id: string;
  domain_id?: string;
  status: string;
  title: string;
  detail: string;
  claim_ids?: string[];
  gate_result?: string;
  source?: string;
};

type HistoryEvent = {
  event_id: number;
  event_type: string;
  domain_id?: string | null;
  message: string;
  occurred_at?: string | null;
  data?: Record<string, unknown> | null;
};

export default async function AssessmentPage({
  params,
  searchParams,
}: {
  params: Promise<{ assessmentId: string }>;
  searchParams: Promise<{ tab?: string; kind?: string }>;
}) {
  const { assessmentId } = await params;
  const { tab: rawTab, kind: rawKind } = await searchParams;
  const tab = (TABS.includes(rawTab as (typeof TABS)[number]) ? rawTab : "overview") as string;
  const kind = rawKind?.trim() || undefined;
  const cookie = await sessionCookie();
  const row = cookie
    ? await apiJson<{
        assessment_id: string;
        company_name: string;
        level: number;
        state: string;
        revision: number;
        summary: Record<string, unknown> | null;
        domains?: Array<Record<string, unknown>>;
        recommendation?: string;
        headline?: string;
        measures?: Record<string, unknown>;
        conditions?: string[];
        risks?: Risk[];
        requests?: InfoRequest[];
        history?: HistoryEvent[];
        memo?: Record<string, unknown>;
        review_target?: Record<string, unknown>;
        can_decide?: boolean;
        claim_total?: number;
        contradiction_total?: number;
      }>(`/api/v1/assessments/${assessmentId}`, cookie)
    : null;

  if (!row) {
    return (
      <ResearchShell title="Assessment">
        <p className="err">Assessment not found or session missing.</p>
        <p>
          <Link href="/signin">Sign in</Link>
        </p>
      </ResearchShell>
    );
  }

  const summary = row.summary || {};
  const domains =
    (row.domains as Array<{
      domain_id: string;
      status: string;
      gate_result: string;
      reason?: string | null;
      sources_found: number;
      sources_required: number;
      findings: number;
      contradictions: number;
      risks: number;
      requests: number;
    }>) ||
    (summary.domains as typeof row.domains) ||
    [];
  const api = publicApiBase();
  const claims = cookie
    ? await apiJson<{ items: Array<Record<string, unknown>>; total: number }>(
        `/api/v1/assessments/${assessmentId}/claims?limit=50&revision=${row.revision}`,
        cookie,
      )
    : null;
  const contradictions = cookie
    ? await apiJson<{ items: Array<Record<string, unknown>>; total: number }>(
        `/api/v1/assessments/${assessmentId}/contradictions?limit=50&revision=${row.revision}`,
        cookie,
      )
    : null;

  const risks = (row.risks || (summary.risks as Risk[]) || []) as Risk[];
  const requests = (row.requests || (summary.requests as InfoRequest[]) || []) as InfoRequest[];
  const history = (row.history || (summary.history as HistoryEvent[]) || []) as HistoryEvent[];
  const memo = (row.memo || (summary.memo as Record<string, unknown>) || {}) as Record<
    string,
    unknown
  >;
  const memoSections =
    (memo.sections as Array<{ id: string; title: string; status: string; body?: string }>) || [];
  const domainGates = (summary.domain_gates || {}) as Record<string, string>;
  const llmUsed = Boolean(summary.llm_used);
  const claimLookup: Record<string, string> = {};
  for (const c of claims?.items || []) {
    const id = String(c.claim_id || "");
    if (id) claimLookup[id] = String(c.statement || "");
  }
  const domainsEnriched = (domains as Array<{
    domain_id: string;
    status: string;
    gate_result: string;
    reason?: string | null;
    sources_found: number;
    sources_required: number;
    findings: number;
    contradictions: number;
    risks: number;
    requests: number;
  }>).map((d) => ({
    ...d,
    risks: risks.filter((r) => r.domain_id === d.domain_id).length || d.risks || 0,
    requests: requests.filter((q) => q.domain_id === d.domain_id).length || d.requests || 0,
    findings:
      (claims?.items || []).filter((c) => String(c.domain_id) === d.domain_id).length ||
      d.findings ||
      0,
    contradictions:
      (contradictions?.items || []).filter((c) =>
        Array.isArray(c.domain_ids)
          ? (c.domain_ids as string[]).includes(d.domain_id)
          : false,
      ).length || d.contradictions || 0,
  }));

  const recommendation = String(
    row.recommendation || summary.recommendation || "hold",
  );
  const canDecide = Boolean(row.can_decide) || row.state === "AWAITING_REVIEW";
  const sourceHosts = Array.from(
    new Set(
      (claims?.items || []).flatMap((c) =>
        Array.isArray(c.source_urls)
          ? (c.source_urls as unknown[])
              .map(String)
              .filter((u) => u.startsWith("http") && !u.endsWith("/mirror"))
              .map((u) => {
                try {
                  return new URL(u).hostname.replace(/^www\./, "");
                } catch {
                  return "";
                }
              })
              .filter(Boolean)
          : [],
      ),
    ),
  );

  return (
    <ResearchShell
      title={row.company_name}
      crumbs={["Companies", row.company_name]}
      demo={!(llmUsed || (claims?.total || 0) > 0 || (row.claim_total || 0) > 0)}
    >
      <div className="ph">
        <div className="hstack-start">
          <span className="logo logo-lg">{initials(row.company_name)}</span>
          <div className="vstack">
            <div className="hstack-wrap">
              <h1>{row.company_name}</h1>
              <span className="lvl">L{row.level}</span>
              <StatusPill color={researchModeColor(llmUsed)}>
                {agentModeLabel(llmUsed)}
              </StatusPill>
            </div>
            <p className="sub">
              {levelLabel(row.level)} · {stateLabel(row.state)} · rev {row.revision} ·{" "}
              {assessmentId.slice(0, 8)}…
            </p>
          </div>
        </div>
        <div className="hstack-wrap">
          <RestartScreenButton
            apiBase={api}
            assessmentId={assessmentId}
            state={row.state}
            level={row.level}
          />
          <DeepenLevelButton
            apiBase={api}
            assessmentId={assessmentId}
            level={row.level}
            state={row.state}
          />
          <DecideChrome
            companyName={row.company_name}
            level={row.level}
            revision={row.revision}
            apiBase={api}
            assessmentId={assessmentId}
            target={(row.review_target || summary.review_target || null) as never}
            state={row.state}
            canDecide={canDecide}
            draftRequests={requests
              .map((q) => {
                const title = String(q.title || "").trim();
                const detail = String(q.detail || "").trim();
                if (title && detail && !detail.startsWith(title)) return `${title}: ${detail}`;
                return title || detail;
              })
              .filter(Boolean)}
          />
        </div>
      </div>

      <nav className="tabs sticky" aria-label="Diligence sections">
        {TABS.map((t) => (
          <Link
            key={t}
            href={`/companies/a/${assessmentId}?tab=${t}`}
            className={`tab${tab === t ? " on" : ""}`}
          >
            {tabCopy[t] || t}
          </Link>
        ))}
      </nav>

      {tab === "overview" && (
        <>
          <div className="overview-split">
            <section className="card inkcard ink-hero">
              <span className="lbl">Partner suggestion (agent-assisted)</span>
              <span className="disp">{recLabel(recommendation)}</span>
              <p className="mute flush" style={{ maxWidth: 560, color: "inherit", opacity: 0.85 }}>
                {String(
                  row.headline ||
                    summary.headline ||
                    recBlurb(recommendation) ||
                    "Public findings available for partner review.",
                )}
              </p>
              <p className="mute mute-sm flush" style={{ opacity: 0.75 }}>
                {recBlurb(recommendation)} Not an investment recommendation.
              </p>
              {(() => {
                const conditions = (row.conditions ||
                  summary.conditions ||
                  []) as string[];
                if (!conditions.length) return null;
                return (
                  <ul className="list-cond">
                    {conditions.map((c) => (
                      <li key={c}>{c}</li>
                    ))}
                  </ul>
                );
              })()}
            </section>
            <section className="card" style={{ flex: "1 1 280px", minWidth: 0 }}>
              <div className="ch">
                <h2>Partner next steps</h2>
                <span className="lbl">IC flow</span>
              </div>
              <div className="cb stack">
                {canDecide ? (
                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    <span style={{ fontWeight: 600 }}>Record the firm decision</span>
                    <span className="mute" style={{ fontSize: 13 }}>
                      Suggested call: {recLabel(recommendation)}. Partners decide; agents only
                      brief.
                    </span>
                    <Link className="btn btn-primary btn-sm" href={`#review`}>
                      Decide
                    </Link>
                  </div>
                ) : null}
                {row.level < 3 ? (
                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    <span style={{ fontWeight: 600 }}>
                      Deepen diligence (Level {row.level + 1})
                    </span>
                    <span className="mute" style={{ fontSize: 13 }}>
                      {row.level === 1
                        ? "Adds competition, traction, capitalization, legal, security and governance on public sources."
                        : "Opens the data room; runs all 12 domains including public financials. Private-document agent analysis stays off."}
                    </span>
                    <DeepenLevelButton
                      apiBase={api}
                      assessmentId={assessmentId}
                      level={row.level}
                      state={row.state}
                    />
                  </div>
                ) : null}
                {(contradictions?.total || 0) > 0 ? (
                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    <span style={{ fontWeight: 600 }}>Clear contested findings</span>
                    <span className="mute" style={{ fontSize: 13 }}>
                      {contradictions?.total} contested item
                      {(contradictions?.total || 0) === 1 ? "" : "s"} need a partner call.
                    </span>
                    <Link
                      className="btn btn-sm"
                      href={`/companies/a/${assessmentId}?tab=contradictions`}
                    >
                      Review contested
                    </Link>
                  </div>
                ) : null}
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  <span style={{ fontWeight: 600 }}>Read the findings pack</span>
                  <span className="mute" style={{ fontSize: 13 }}>
                    Workstreams → findings with cited pages → memo.
                  </span>
                  <Link
                    className="btn btn-sm"
                    href={`/companies/a/${assessmentId}?tab=sources`}
                  >
                    Open findings
                  </Link>
                </div>
              </div>
            </section>
          </div>
          <ResearchBrief
            assessmentId={assessmentId}
            recommendation={recommendation}
            domainGates={domainGates}
            claimTotal={row.claim_total ?? claims?.total ?? 0}
            contradictionTotal={row.contradiction_total ?? contradictions?.total ?? 0}
            llmUsed={llmUsed}
            sourceHosts={sourceHosts}
          />
          <VerdictStrip
            recommendation={recommendation}
            conditions={(row.conditions || summary.conditions || []) as string[]}
            headline={(row.headline || summary.headline) as string}
            level={row.level}
            state={row.state}
          />
          <MeasuresRow measures={(row.measures || summary.measures) as never} />
          <FindingKindBar
            assessmentId={assessmentId}
            counts={{
              supported: claims?.items?.filter((c) => c.trust_state === "supported").length || 0,
              contra:
                (contradictions?.total || 0) +
                (claims?.items?.filter((c) => c.trust_state === "contested").length || 0),
              verified:
                claims?.items?.filter((c) => c.verification_status === "verified").length || 0,
              inference:
                claims?.items?.filter((c) => c.trust_state === "unsupported").length || 0,
              missing:
                claims?.items?.filter(
                  (c) =>
                    c.trust_state === "insufficient" ||
                    c.verification_status === "insufficient",
                ).length || 0,
              calc:
                claims?.items?.filter((c) => {
                  const t = String(c.claim_type || "").toLowerCase();
                  const nums = (c as { numeric_facts?: string[] }).numeric_facts;
                  return (
                    t.includes("calc") ||
                    t.includes("metric") ||
                    t.includes("financial") ||
                    (Array.isArray(nums) && nums.length > 0)
                  );
                }).length || 0,
              // Risks are agent gap products, not claim findings — keep out of the bar.
            }}
          />
          <ProgressPanel assessmentId={assessmentId} apiBase={api} />
          <SanctionsCard companyName={row.company_name} />
          <div id="review">
            <ReviewPanel
              apiBase={api}
              assessmentId={assessmentId}
              revision={row.revision}
              state={row.state}
              target={(row.review_target || summary.review_target || null) as never}
              draftRequests={requests
                .map((q) => {
                  const title = String(q.title || "").trim();
                  const detail = String(q.detail || "").trim();
                  if (title && detail && !detail.startsWith(title)) return `${title}: ${detail}`;
                  return title || detail;
                })
                .filter(Boolean)}
            />
          </div>
        </>
      )}

      {tab === "domains" && (
        <>
          <DomainTable domains={domainsEnriched as never} />
          <SanctionsCard companyName={row.company_name} />
        </>
      )}

      {tab === "report" && (
        <>
          <section className="card">
            <div className="ch">
              <h2>Investment memo (draft)</h2>
              <span className="mono lbl">{String(memo.schema || "ddreport@1-scaffold")}</span>
            </div>
            <div className="cb">
              <p className="lede" style={{ margin: 0 }}>
                {String(summary.headline || row.headline || "—")}
              </p>
              <p className="mute" style={{ margin: "8px 0 0", fontSize: 13 }}>
                Draft for partner review. Cite findings before relying on any number.
              </p>
            </div>
            <div className="row">
              <span>Partner suggestion</span>
              <span>{recLabel(recommendation)}</span>
            </div>
            <div className="row">
              <span>Findings / contested</span>
              <span>
                {row.claim_total ?? claims?.total ?? 0} findings ·{" "}
                {row.contradiction_total ?? contradictions?.total ?? 0} contested
              </span>
            </div>
            <div className="row">
              <span>Research mode</span>
              <span>
                {agentModeDetail(llmUsed)}
              </span>
            </div>
            <div className="row">
              <span>Workstream bars</span>
              <span>
                {Object.entries(domainGates)
                  .map(([k, v]) => `${k}: ${v}`)
                  .join(" · ") || "—"}
              </span>
            </div>
            <div className="row">
              <span>Notice</span>
              <span className="mute">
                {String(
                  memo.notice ||
                    "Automated diligence support; not legal, accounting, or investment advice.",
                )}
              </span>
            </div>
          </section>
          <section className="card">
            <div className="ch">
              <h2>Memo sections</h2>
              <span className="lbl">{levelLabel(row.level)} coverage</span>
            </div>
            {(memoSections.length
              ? memoSections
              : Object.keys(domainGates).map((id) => ({
                  id,
                  title: id.replace(/_/g, " "),
                  status: domainGates[id],
                  body: undefined as string | undefined,
                }))
            ).map((s) => {
              const body = typeof s.body === "string" ? s.body : "";
              const statusLabel =
                s.status === "sufficient"
                  ? "Cleared"
                  : s.status === "partial"
                    ? "Needs more"
                    : s.status === "insufficient"
                      ? "Open gap"
                      : String(s.status || "—");
              return (
              <div
                key={s.id}
                className="li"
                style={{ display: "flex", flexDirection: "column", gap: 6 }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                  <span style={{ textTransform: "capitalize", fontWeight: 600 }}>{s.title}</span>
                  <span className="pill">
                    <span
                      className="dot"
                      style={{
                        background:
                          s.status === "sufficient"
                            ? "var(--green)"
                            : s.status === "partial"
                              ? "var(--amber)"
                              : s.status === "insufficient"
                                ? "var(--red)"
                                : "var(--gray)",
                      }}
                    />
                    {statusLabel}
                  </span>
                </div>
                {body ? (
                  <p className="mute flush" style={{ margin: 0, maxWidth: 720 }}>
                    {body}
                  </p>
                ) : null}
              </div>
              );
            })}
          </section>
        </>
      )}

      {tab === "contradictions" && (
        <ContradictionResolvePanel
          apiBase={api}
          claimLookup={claimLookup}
          items={(contradictions?.items || []).map((c) => ({
            contradiction_id: String(c.contradiction_id),
            severity: String(c.severity),
            contradiction_type: String(c.contradiction_type),
            explanation: String(c.explanation),
            resolution: String(c.resolution),
            version: Number(c.version || 1),
            human_review_state: c.human_review_state ? String(c.human_review_state) : undefined,
            domain_ids: Array.isArray(c.domain_ids)
              ? (c.domain_ids as unknown[]).map(String)
              : [],
            claim_ids: Array.isArray(c.claim_ids)
              ? (c.claim_ids as unknown[]).map(String)
              : [],
            evidence_for: Array.isArray(c.evidence_for)
              ? (c.evidence_for as unknown[]).map(String)
              : [],
            evidence_against: Array.isArray(c.evidence_against)
              ? (c.evidence_against as unknown[]).map(String)
              : [],
          }))}
        />
      )}

      {tab === "risks" && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 16, alignItems: "flex-start" }}>
          <section className="card" style={{ flex: "1 1 260px", minWidth: 0 }}>
            <div className="ch">
              <h2>Severity × likelihood</h2>
              <span className="lbl">From agent gates</span>
            </div>
            <div className="cb">
              <div className="mx">
                {(() => {
                  const sev = ["high", "medium", "low"] as const;
                  const lik = ["high", "medium", "low"] as const;
                  const cells: ReactNode[] = [
                    <span key="c0" />,
                    ...lik.map((l) => (
                      <span key={`h-${l}`} className="lbl">
                        {l}
                      </span>
                    )),
                  ];
                  for (const s of sev) {
                    cells.push(
                      <span key={`r-${s}`} className="lbl">
                        {s}
                      </span>,
                    );
                    for (const l of lik) {
                      const n = risks.filter(
                        (r) =>
                          (r.severity || "").toLowerCase() === s &&
                          normalizeLikelihood(r.likelihood) === l,
                      ).length;
                      const bg =
                        n === 0
                          ? "var(--surface-2)"
                          : s === "high"
                            ? "color-mix(in srgb, var(--red) 22%, var(--surface))"
                            : s === "medium"
                              ? "color-mix(in srgb, var(--amber) 22%, var(--surface))"
                              : "color-mix(in srgb, var(--green) 18%, var(--surface))";
                      cells.push(
                        <span key={`${s}-${l}`} style={{ background: bg, fontWeight: n ? 600 : 400 }}>
                          {n || "·"}
                        </span>,
                      );
                    }
                  }
                  return cells;
                })()}
              </div>
              <p className="lbl" style={{ margin: "10px 0 0" }}>
                Live counts from agent workstream gaps — not seeded mock risks.
              </p>
            </div>
          </section>
          <section className="card" style={{ flex: "999 1 560px", minWidth: 0 }}>
            <div className="ch">
              <h2>Risk register</h2>
              <span className="lbl">
                {risks.length} from research · each cites agent findings
              </span>
            </div>
            {!risks.length ? (
              <div className="cb">
                <p className="mute" style={{ margin: 0 }}>
                  No agent-derived risks yet — run or finish public research first.
                </p>
              </div>
            ) : (
              risks.map((r) => {
                const dot =
                  r.severity === "high"
                    ? "var(--red)"
                    : r.severity === "medium"
                      ? "var(--amber)"
                      : "var(--gray)";
                const lik = normalizeLikelihood(r.likelihood);
                return (
                  <div
                    key={r.id}
                    className="li"
                    style={{ display: "flex", flexWrap: "wrap", gap: "8px 16px", alignItems: "center" }}
                  >
                    <span className="pill" style={{ ["--c" as string]: dot, minWidth: 74 }}>
                      <span className="dot" style={{ background: dot }} />
                      {r.severity}
                    </span>
                    <span style={{ flex: "1 1 320px", display: "flex", flexDirection: "column", gap: 4 }}>
                      <span style={{ fontWeight: 500 }}>{r.title}</span>
                      <span className="lbl">
                        {r.domain_id || "—"} · likelihood {lik}
                        {r.gate_result ? ` · gate ${r.gate_result}` : ""}
                        {r.source ? ` · ${r.source}` : ""}
                      </span>
                      <span className="lbl">{r.detail}</span>
                      {(r.source_hosts || []).length ? (
                        <span className="lbl">Sources: {(r.source_hosts || []).join(" · ")}</span>
                      ) : null}
                      {(r.claim_ids || []).length ? (
                        <Link
                          className="lbl"
                          href={`/companies/a/${assessmentId}?tab=sources`}
                          style={{ color: "var(--brand-text, var(--brand))" }}
                        >
                          Open {(r.claim_ids || []).length} linked finding
                          {(r.claim_ids || []).length === 1 ? "" : "s"}
                        </Link>
                      ) : null}
                    </span>
                  </div>
                );
              })
            )}
          </section>
        </div>
      )}

      {tab === "requests" && (
        <section className="card">
          <div className="ch">
            <h2>Information asks</h2>
            <span className="lbl">{requests.length} drafted from agent gaps</span>
          </div>
          {!requests.length ? (
            <div className="cb">
              <p className="mute" style={{ margin: 0 }}>
                No asks drafted — agent workstreams are cleared or research has not finished.
              </p>
            </div>
          ) : (
            <>
              {requests.map((q) => (
                <div key={q.id} className="li" style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                    <span style={{ fontWeight: 600 }}>{q.title}</span>
                    <span className="pill">
                      <span className="dot" />
                      {q.status}
                    </span>
                  </div>
                  <span className="lbl">
                    {q.domain_id ? `${q.domain_id} · ` : ""}
                    {q.gate_result ? `gate ${q.gate_result} · ` : ""}
                    {q.detail}
                  </span>
                  {(q.claim_ids || []).length ? (
                    <Link
                      className="lbl"
                      href={`/companies/a/${assessmentId}?tab=sources`}
                      style={{ color: "var(--brand-text, var(--brand))" }}
                    >
                      View linked findings
                    </Link>
                  ) : null}
                </div>
              ))}
              <div className="lbl" style={{ padding: "10px 18px", borderTop: "1px solid var(--border)" }}>
                Agents draft these from open workstream gaps; the deal team sends them. The system
                never emails the company.
              </div>
            </>
          )}
        </section>
      )}

      {tab === "dataroom" && (
        <>
          <section className="card">
            <div className="ch">
              <h2>Data room</h2>
              <span className="pill">
                <span
                  className="dot"
                  style={{
                    background:
                      row.level >= 3 &&
                      Boolean(
                        (row as { dataroom?: { upload_enabled?: boolean } }).dataroom
                          ?.upload_enabled ??
                          (summary.dataroom as { upload_enabled?: boolean } | undefined)
                            ?.upload_enabled,
                      )
                        ? "var(--green)"
                        : "var(--amber)",
                  }}
                />
                {row.level < 3
                  ? "public evidence"
                  : Boolean(
                        (row as { dataroom?: { upload_enabled?: boolean } }).dataroom
                          ?.upload_enabled ??
                          (summary.dataroom as { upload_enabled?: boolean } | undefined)
                            ?.upload_enabled,
                      )
                    ? "uploads enabled"
                    : "scanner unavailable"}
              </span>
            </div>
            <div className="cb">
              <p className="mute" style={{ margin: 0 }}>
                {String(
                  (row as { dataroom?: { notice?: string } }).dataroom?.notice ||
                    (summary.dataroom as { notice?: string } | undefined)?.notice ||
                    (row.level < 3
                      ? "Level 1/2 lists public pages already fetched — not private uploads."
                      : "Restricted to the deal team. Uploads require healthy ClamAV."),
                )}
              </p>
            </div>
            <div className="row">
              <span>Private uploads</span>
              <span>
                {row.level < 3
                  ? "locked until Level 3"
                  : Boolean(
                        (row as { dataroom?: { upload_enabled?: boolean } }).dataroom
                          ?.upload_enabled ??
                          (summary.dataroom as { upload_enabled?: boolean } | undefined)
                            ?.upload_enabled,
                      )
                    ? "ClamAV-gated"
                    : "SCANNER_UNAVAILABLE"}
              </span>
            </div>
            <div className="row">
              <span>ClamAV / OCR parse</span>
              <span>
                {row.level < 3
                  ? "n/a"
                  : Boolean(
                        (row as { dataroom?: { upload_enabled?: boolean } }).dataroom
                          ?.upload_enabled ??
                          (summary.dataroom as { upload_enabled?: boolean } | undefined)
                            ?.upload_enabled,
                      )
                    ? "scan + PDF parse online · q.docs Verified open"
                    : "waiting for ClamAV"}
              </span>
            </div>
            <div className="row">
              <span>Public pages retrieved</span>
              <span>
                {(row as { dataroom?: { document_count?: number } }).dataroom?.document_count ??
                  (summary.dataroom as { document_count?: number } | undefined)?.document_count ??
                  0}
              </span>
            </div>
          </section>
          {row.level >= 3 && (
            <DataRoomUpload
              apiBase={publicApiBase()}
              assessmentId={assessmentId}
              uploadEnabled={Boolean(
                (row as { dataroom?: { upload_enabled?: boolean } }).dataroom?.upload_enabled ??
                  (summary.dataroom as { upload_enabled?: boolean } | undefined)?.upload_enabled,
              )}
              notice={
                (row as { dataroom?: { notice?: string } }).dataroom?.notice ||
                (summary.dataroom as { notice?: string } | undefined)?.notice
              }
              initialDocs={
                ((row as { dataroom?: { private_documents?: Array<Record<string, unknown>> } })
                  .dataroom?.private_documents ||
                  (summary.dataroom as { private_documents?: Array<Record<string, unknown>> } | undefined)
                    ?.private_documents ||
                  []) as Array<{
                  document_id: string;
                  filename: string;
                  status: string;
                  byte_size?: number;
                  ocr_pages?: number | null;
                  scan_detail?: string | null;
                }>
              }
            />
          )}
          <section className="card">
            <div className="ch">
              <h2>Public evidence inventory</h2>
              <span className="lbl">SafeFetch snapshots cited by claims</span>
            </div>
            {(() => {
              const docs =
                (
                  (row as { dataroom?: { documents?: Array<Record<string, unknown>> } }).dataroom
                    ?.documents ||
                  (summary.dataroom as { documents?: Array<Record<string, unknown>> } | undefined)
                    ?.documents ||
                  []
                ) as Array<{
                  url: string;
                  status: string;
                  domains: string[];
                  claim_count: number;
                  snapshot_count: number;
                }>;
              if (!docs.length) {
                return (
                  <div className="cb">
                    <p className="mute" style={{ margin: 0 }}>
                      No public evidence pages persisted yet.
                    </p>
                  </div>
                );
              }
              return (
                <table className="table">
                  <thead>
                    <tr>
                      <th>Source</th>
                      <th>Status</th>
                      <th>Domains</th>
                      <th>Claims</th>
                      <th>Snapshots</th>
                    </tr>
                  </thead>
                  <tbody>
                    {docs.map((d) => (
                      <tr key={d.url}>
                        <td className="mono" style={{ fontSize: 12 }}>
                          <a href={d.url} target="_blank" rel="noreferrer">
                            {d.url}
                          </a>
                        </td>
                        <td>{d.status}</td>
                        <td>{(d.domains || []).join(", ") || "—"}</td>
                        <td>{d.claim_count}</td>
                        <td>{d.snapshot_count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              );
            })()}
          </section>
        </>
      )}

      {tab === "financials" && (
        <>
          <section className="card">
            <div className="ch">
              <h2>Financials</h2>
              <span className="pill">
                <span className="dot" style={{ background: "var(--amber)" }} />
                {row.level < 3 ? "public signals only" : "private gated"}
              </span>
            </div>
            <div className="cb">
              <p className="mute" style={{ margin: 0 }}>
                {String(
                  (row as { financials?: { notice?: string } }).financials?.notice ||
                    (summary.financials as { notice?: string } | undefined)?.notice ||
                    "Calculated ARR/burn require Level 3 workbooks from the agent path.",
                )}
              </p>
            </div>
          </section>
          <section className="card">
            <div className="ch">
              <h2>Calculated metrics</h2>
              <span className="lbl">From agent financials payload · not UI mock</span>
            </div>
            {(() => {
              const metrics = ((
                (row as { financials?: { metrics?: Array<Record<string, unknown>> } }).financials
                  ?.metrics ||
                (summary.financials as { metrics?: Array<Record<string, unknown>> } | undefined)
                  ?.metrics ||
                []
              ) as Array<{
                metric: string;
                value: string | number | null;
                status: string;
                note?: string;
              }>);
              const valued = metrics.filter(
                (m) => m.value != null && String(m.value).trim() !== "" && m.value !== "—",
              );
              if (!valued.length) {
                return (
                  <div className="cb">
                    <p className="mute" style={{ margin: 0 }}>
                      No calculated ARR/burn yet. Level 3 public screen shows funding signals below;
                      workbook-derived metrics stay empty until a verified financial workbook is
                      ingested (private AI remains off).
                    </p>
                  </div>
                );
              }
              return (
                <table className="table">
                  <thead>
                    <tr>
                      <th>Metric</th>
                      <th>Value</th>
                      <th>Status</th>
                      <th>Note</th>
                    </tr>
                  </thead>
                  <tbody>
                    {valued.map((m) => (
                      <tr key={m.metric}>
                        <td>{m.metric}</td>
                        <td className="mono">{m.value ?? "—"}</td>
                        <td>{m.status}</td>
                        <td className="mute">{m.note || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              );
            })()}
          </section>
          <section className="card">
            <div className="ch">
              <h2>Public financial signals</h2>
              <span className="lbl">unvalidated agent claims</span>
            </div>
            {(() => {
              const signals =
                (
                  (
                    row as {
                      financials?: { public_signals?: Array<Record<string, unknown>> };
                    }
                  ).financials?.public_signals ||
                  (
                    summary.financials as
                      | { public_signals?: Array<Record<string, unknown>> }
                      | undefined
                  )?.public_signals ||
                  []
                ) as Array<{
                  statement: string;
                  domain_id: string;
                  trust_state: string;
                  source_url?: string | null;
                  label: string;
                }>;
              if (!signals.length) {
                return (
                  <div className="cb">
                    <p className="mute" style={{ margin: 0 }}>
                      No public claims mentioned funding, ARR, users, or similar scale signals.
                    </p>
                  </div>
                );
              }
              return (
                <table className="table">
                  <thead>
                    <tr>
                      <th>Domain</th>
                      <th>Claim</th>
                      <th>Trust</th>
                      <th>Source</th>
                      <th>Validated</th>
                    </tr>
                  </thead>
                  <tbody>
                    {signals.map((s, i) => (
                      <tr key={`${s.domain_id}-${i}`}>
                        <td>{s.domain_id}</td>
                        <td>{s.statement}</td>
                        <td>{s.trust_state}</td>
                        <td className="mono" style={{ fontSize: 12 }}>
                          {s.source_url ? (
                            <a href={s.source_url} target="_blank" rel="noreferrer">
                              {s.source_url}
                            </a>
                          ) : (
                            "—"
                          )}
                        </td>
                        <td>no</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              );
            })()}
          </section>
        </>
      )}

      {tab === "sources" && (
        <ClaimsSourcesPanel
          apiBase={api}
          kind={kind}
          items={(claims?.items || []).map((c) => ({
            claim_id: String(c.claim_id),
            domain_id: String(c.domain_id),
            statement: String(c.statement || ""),
            trust_state: String(c.trust_state || ""),
            verification_status: String(c.verification_status || ""),
            confidence: c.confidence as number | string | null | undefined,
            evidence_quality: c.evidence_quality ? String(c.evidence_quality) : null,
            claim_type: c.claim_type ? String(c.claim_type) : null,
            company_authored: Boolean(c.company_authored),
            source_urls: Array.isArray(c.source_urls)
              ? (c.source_urls as unknown[]).map(String)
              : [],
            snapshot_ids: Array.isArray(c.snapshot_ids)
              ? (c.snapshot_ids as unknown[]).map(String)
              : [],
            evidence_span_ids: Array.isArray(c.evidence_span_ids)
              ? (c.evidence_span_ids as unknown[]).map(String)
              : [],
            numeric_facts: Array.isArray(c.numeric_facts)
              ? (c.numeric_facts as unknown[]).map(String)
              : [],
            numeric_facts_grounded: Array.isArray(c.numeric_facts_grounded)
              ? (c.numeric_facts_grounded as unknown[]).map(String)
              : [],
          }))}
        />
      )}

      {tab === "history" && (
        <section className="card">
          <div className="ch">
            <h2>History</h2>
            <span className="lbl">{history.length} durable events · rev {row.revision}</span>
          </div>
          {!history.length ? (
            <div className="cb">
              <p className="mute" style={{ margin: 0 }}>
                No progress events recorded.
              </p>
            </div>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>When</th>
                  <th>Type</th>
                  <th>Domain</th>
                  <th>Message</th>
                  <th>Signals</th>
                </tr>
              </thead>
              <tbody>
                {[...history].reverse().map((e) => {
                  const d = e.data || {};
                  const bits = [
                    typeof d.evidence_sufficiency === "string"
                      ? `gate=${d.evidence_sufficiency}`
                      : null,
                    agentSignalTag(d.llm_used === true),
                    d.fetched === true ? "fetched" : d.fetched === false ? "stub" : null,
                    typeof d.independent_count === "number"
                      ? `indep=${d.independent_count}`
                      : null,
                    typeof d.status === "string" ? `status=${d.status}` : null,
                  ].filter(Boolean);
                  return (
                    <tr key={e.event_id}>
                      <td className="mono" style={{ fontSize: 12 }}>
                        {e.occurred_at
                          ? new Date(e.occurred_at).toLocaleString("en-GB", {
                              day: "numeric",
                              month: "short",
                              hour: "2-digit",
                              minute: "2-digit",
                            })
                          : "—"}
                      </td>
                      <td>{e.event_type}</td>
                      <td>{e.domain_id || "—"}</td>
                      <td>{e.message}</td>
                      <td className="mute">{bits.length ? bits.join(" · ") : "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </section>
      )}
    </ResearchShell>
  );
}
