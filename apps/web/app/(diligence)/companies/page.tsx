import Link from "next/link";
import ResearchShell from "@/components/shell/ResearchShell";
import StatusPill from "@/components/ui/StatusPill";
import { apiJson } from "@/lib/api";
import { assessmentStateColor, initials } from "@/lib/format";
import { sessionCookie } from "@/lib/session";
import { stateLabel } from "@/lib/status-copy";

export default async function CompaniesPage() {
  const cookie = await sessionCookie();
  const dash = cookie
    ? await apiJson<{ kpis: { pending_decisions: number } }>("/api/v1/dashboard/summary", cookie)
    : null;
  const companies = cookie
    ? await apiJson<{
        items: Array<{
          company_name: string;
          latest_assessment_id: string;
          level: number;
          state: string;
          revision: number;
        }>;
      }>("/api/v1/companies", cookie)
    : null;

  const items = companies?.items || [];
  const ready = items.filter((c) => c.state === "AWAITING_REVIEW" || c.state === "MEMO_READY").length;
  const progress = items.filter((c) =>
    ["CREATED", "PLANNING", "RESEARCHING", "VALIDATING", "EVALUATING", "CRITIQUING"].includes(c.state),
  ).length;
  const decided = items.filter((c) => c.state === "COMPLETED").length;

  return (
    <ResearchShell title="Companies" pendingDecisions={dash?.kpis.pending_decisions || 0} demo>
      <div className="ph">
        <div>
          <h1>Companies</h1>
          <p className="sub">
            Every company your firm has assessed or is watching. Open one to see its report and what
            to do next.
          </p>
        </div>
        <Link className="btn btn-primary" href="/companies/new">
          New diligence
        </Link>
      </div>

      <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
        {[
          { label: "All", n: items.length },
          { label: "Ready", n: ready },
          { label: "In progress", n: progress },
          { label: "Decided", n: decided },
        ].map((f) => (
          <span key={f.label} className="chip">
            {f.label} <strong style={{ fontWeight: 600 }}>{f.n}</strong>
          </span>
        ))}
      </div>

      <section className="card">
        <div className="ch">
          <h2>Portfolio</h2>
          <span className="lbl">Sorted by last update</span>
        </div>
        {!items.length ? (
          <div className="cb">
            <p className="mute" style={{ margin: 0 }}>
              No companies yet. Start an assessment to begin.
            </p>
          </div>
        ) : (
          <>
            <div
              className="thd"
              style={{ gridTemplateColumns: "40px 1.8fr 72px 1.3fr 64px" }}
            >
              <span />
              <span>Company</span>
              <span>Level</span>
              <span>Status</span>
              <span>Rev</span>
            </div>
            {items.map((c) => (
              <Link
                key={c.latest_assessment_id}
                href={`/companies/a/${c.latest_assessment_id}`}
                className="tr"
                style={{ gridTemplateColumns: "40px 1.8fr 72px 1.3fr 64px" }}
              >
                <span className="logo">{initials(c.company_name)}</span>
                <span style={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 0 }}>
                  <span style={{ fontWeight: 600 }}>{c.company_name}</span>
                  <span className="lbl">Assessment {c.latest_assessment_id.slice(0, 8)}…</span>
                </span>
                <span className="lvl">L{c.level}</span>
                <StatusPill color={assessmentStateColor(c.state)}>
                  {stateLabel(c.state)}
                </StatusPill>
                <span className="mono">{c.revision}</span>
              </Link>
            ))}
          </>
        )}
      </section>
    </ResearchShell>
  );
}
