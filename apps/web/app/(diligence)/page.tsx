import Link from "next/link";
import ResearchShell from "@/components/shell/ResearchShell";
import StatusPill from "@/components/ui/StatusPill";
import { apiJson } from "@/lib/api";
import { initials } from "@/lib/format";
import { sessionCookie } from "@/lib/session";
import { stateLabel } from "@/lib/status-copy";

function progressPct(state: string): number {
  const order = [
    "CREATED",
    "PLANNING",
    "RESEARCHING",
    "VALIDATING",
    "EVALUATING",
    "CRITIQUING",
    "MEMO_READY",
    "AWAITING_REVIEW",
  ];
  const i = order.indexOf(state);
  if (i < 0) return state === "COMPLETED" ? 100 : 12;
  return Math.round(((i + 1) / order.length) * 100);
}

export default async function HomePage() {
  const cookie = await sessionCookie();
  const status = await apiJson<Record<string, unknown>>("/api/v1/system/status");
  const dash = cookie
    ? await apiJson<{
        kpis: Record<string, number>;
        pending_reviews: Array<{
          assessment_id: string;
          company_name: string;
          headline?: string;
          recommendation?: string;
        }>;
        active_assessments: Array<{
          assessment_id: string;
          company_name: string;
          level: number;
          state: string;
          headline?: string;
        }>;
        recent_changes?: Array<{
          assessment_id: string;
          company_name: string;
          summary: string;
          when?: string | null;
          next?: string;
          state?: string;
        }>;
      }>("/api/v1/dashboard/summary", cookie)
    : null;

  const pending = dash?.kpis.pending_decisions ?? 0;
  const greeting =
    pending > 0
      ? `${pending} compan${pending === 1 ? "y is" : "ies are"} ready for your decision. Start with the oldest.`
      : "Your diligence workspace is ready.";
  const today = new Date().toLocaleDateString("en-GB", {
    weekday: "long",
    day: "numeric",
    month: "long",
  });
  const queueCount = dash?.pending_reviews?.length ?? 0;

  return (
    <ResearchShell
      title="Home"
      pendingDecisions={pending}
      demo={Boolean(status?.demo_workspace)}
      mode={String(status?.mode || "")}
    >
      <div className="page-stack">
        <div className="ph">
          <div>
            <span className="lbl">{today}</span>
            <h1 style={{ marginTop: 2 }}>Good morning</h1>
            <p className="sub">{greeting}</p>
          </div>
          <Link className="btn" href="/decisions">
            Review decisions
          </Link>
        </div>

        <div className="kpi-row">
          <Link className="card kpi" href="/companies">
            <span className="lbl">Active</span>
            <span className="v">{dash?.kpis.active_assessments ?? "—"}</span>
            <span className="lbl">Assessments running</span>
          </Link>
          <Link className="card kpi" href="/decisions">
            <span className="lbl">Needs you</span>
            <span className="v">{dash?.kpis.pending_decisions ?? "—"}</span>
            <span className="lbl">Pending decisions</span>
          </Link>
          <div className="card kpi">
            <span className="lbl">Completed</span>
            <span className="v">{dash?.kpis.completed ?? "—"}</span>
            <span className="lbl">Closed assessments</span>
          </div>
          <Link className="card kpi" href="/watchlist">
            <span className="lbl">Watchlist</span>
            <span className="v">{dash?.kpis.watchlist ?? "—"}</span>
            <span className="lbl">Monitored companies</span>
          </Link>
        </div>

        <section className="card">
          <div className="ch">
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <h2>Needs you</h2>
              {queueCount > 0 ? <span className="badge">{queueCount}</span> : null}
            </div>
            <span className="lbl">Decisions, checks and blocked work in one list, oldest first</span>
          </div>
          {!dash?.pending_reviews?.length ? (
            <div className="cb">
              <p className="mute flush">Nothing waiting on you right now.</p>
            </div>
          ) : (
            dash.pending_reviews.map((r) => (
              <div key={r.assessment_id} className="qrow">
                <span className="logo">{initials(r.company_name)}</span>
                <span className="vstack" style={{ flex: "1 1 280px", gap: 3 }}>
                  <span className="hstack-wrap">
                    <span style={{ fontWeight: 600 }}>{r.company_name}</span>
                    <StatusPill color="var(--brand)">Decision</StatusPill>
                  </span>
                  <span className="mute mute-sm">
                    {r.headline || "Ready for your decision"}
                  </span>
                </span>
                <Link className="btn btn-sm btn-primary" href={`/companies/a/${r.assessment_id}`}>
                  Decide
                </Link>
              </div>
            ))
          )}
        </section>

        <div className="overview-split">
          <section className="card" style={{ flex: "1 1 420px", minWidth: 0 }}>
            <div className="ch">
              <h2>In progress</h2>
              <StatusPill color="var(--green)">Live</StatusPill>
            </div>
            {!dash?.active_assessments?.length ? (
              <div className="cb">
                <p className="mute flush">No active assessments.</p>
              </div>
            ) : (
              dash.active_assessments.map((a) => {
                const pct = progressPct(a.state);
                return (
                  <Link
                    key={a.assessment_id}
                    href={`/companies/a/${a.assessment_id}`}
                    className="li vstack"
                    style={{ gap: 8, textDecoration: "none", color: "inherit" }}
                  >
                    <div className="hstack" style={{ justifyContent: "space-between" }}>
                      <span style={{ fontWeight: 500 }}>{a.company_name}</span>
                      <StatusPill color="var(--blue)">{stateLabel(a.state)}</StatusPill>
                    </div>
                    <div className="bar">
                      <span className="fill" style={{ width: `${pct}%` }} />
                    </div>
                    <span className="lbl">
                      Level {a.level} · {a.headline || `${pct}% through screening`}
                    </span>
                  </Link>
                );
              })
            )}
          </section>

          <section className="card" style={{ flex: "1 1 340px", minWidth: 0 }}>
            <div className="ch">
              <h2>What changed</h2>
              <Link className="btn btn-ghost btn-sm" href="/watchlist">
                Watchlist
              </Link>
            </div>
            {!dash?.recent_changes?.length ? (
              <div className="cb">
                <p className="mute" style={{ margin: 0 }}>
                  No recent changes yet.
                </p>
              </div>
            ) : (
              dash.recent_changes.map((e) => (
                <Link
                  key={`${e.assessment_id}-${e.when || e.summary}`}
                  href={`/companies/a/${e.assessment_id}`}
                  className="li"
                  style={{ display: "flex", gap: 12, textDecoration: "none", color: "inherit" }}
                >
                  <span className="dot" style={{ background: "var(--blue)", marginTop: 7 }} />
                  <span style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                    <span style={{ fontWeight: 500 }}>
                      {e.company_name}{" "}
                      <span className="lbl">
                        ·{" "}
                        {e.when
                          ? new Date(e.when).toLocaleString("en-GB", {
                              day: "numeric",
                              month: "short",
                              hour: "2-digit",
                              minute: "2-digit",
                            })
                          : "recently"}
                      </span>
                    </span>
                    <span>{e.summary}</span>
                    <span className="lbl">{e.next || "Open assessment"}</span>
                  </span>
                </Link>
              ))
            )}
          </section>
        </div>
      </div>
    </ResearchShell>
  );
}
