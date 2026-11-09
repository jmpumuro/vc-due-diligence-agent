import Link from "next/link";
import LiveEventTail from "@/components/console/LiveEventTail";
import ConsoleShell from "@/components/shell/ConsoleShell";
import StatusPill from "@/components/ui/StatusPill";
import { apiJson } from "@/lib/api";
import { sessionCookie } from "@/lib/session";
import { stateLabel } from "@/lib/status-copy";

export default async function ConsoleRunsPage() {
  const cookie = await sessionCookie();
  const status = await apiJson<{ mode?: string }>("/api/v1/system/status");
  const runs = cookie
    ? await apiJson<{
        items: Array<{
          assessment_id: string;
          company_name: string;
          level: number;
          state: string;
          revision: number;
          workflow_id?: string;
        }>;
      }>("/api/v1/ops/runs", cookie)
    : null;
  const attention = cookie
    ? await apiJson<{
        outbox_pending: number;
        blocked_or_waiting: Array<{ assessment_id: string; company_name: string; state: string }>;
      }>("/api/v1/ops/attention", cookie)
    : null;

  return (
    <ConsoleShell title="Runs" mode={status?.mode}>
      <div className="ph">
        <div>
          <h1>Runs</h1>
          <p className="sub">Active and recent diligence workflows.</p>
        </div>
      </div>

      <div className="kpi-row">
        <div className="card kpi">
          <span className="lbl">Runs</span>
          <span className="v">{runs?.items.length ?? "—"}</span>
        </div>
        <div className="card kpi">
          <span className="lbl">Needs attention</span>
          <span className="v">{attention?.blocked_or_waiting.length ?? "—"}</span>
        </div>
        <div className="card kpi">
          <span className="lbl">Outbox pending</span>
          <span className="v">{attention?.outbox_pending ?? "—"}</span>
        </div>
      </div>

      <section className="card">
        <div className="ch">
          <h2>Needs action</h2>
        </div>
        {!attention?.blocked_or_waiting?.length ? (
          <div className="cb">
            <p className="mute flush">Queue clear.</p>
          </div>
        ) : (
          attention.blocked_or_waiting.map((r) => (
            <Link
              key={r.assessment_id}
              href={`/companies/a/${r.assessment_id}`}
              className="tr"
              style={{ gridTemplateColumns: "1fr auto auto" }}
            >
              <span style={{ fontWeight: 600 }}>{r.company_name}</span>
              <StatusPill color="var(--amber)">{stateLabel(r.state)}</StatusPill>
              <span className="lbl">Open →</span>
            </Link>
          ))
        )}
      </section>

      <section className="card">
        <div className="ch">
          <h2>Recent runs</h2>
        </div>
        <table className="table">
          <thead>
            <tr>
              <th>Company</th>
              <th>Level</th>
              <th>State</th>
              <th>Workflow</th>
            </tr>
          </thead>
          <tbody>
            {(runs?.items || []).map((r) => (
              <tr key={r.assessment_id}>
                <td>
                  <Link href={`/companies/a/${r.assessment_id}`}>{r.company_name}</Link>
                </td>
                <td>L{r.level}</td>
                <td>{stateLabel(r.state)}</td>
                <td className="mono">{r.workflow_id || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <LiveEventTail />
    </ConsoleShell>
  );
}
