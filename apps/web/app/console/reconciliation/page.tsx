import ConsoleShell from "@/components/shell/ConsoleShell";
import { apiJson } from "@/lib/api";
import { sessionCookie } from "@/lib/session";
import DispatchButton from "./DispatchButton";

export default async function ReconciliationPage() {
  const cookie = await sessionCookie();
  const status = await apiJson<{ mode?: string }>("/api/v1/system/status");
  const outbox = cookie
    ? await apiJson<{
        pending: number;
        items: Array<{ outbox_id: string; event_type: string; subject_id: string; sequence: number }>;
      }>("/api/v1/ops/outbox/summary", cookie)
    : null;

  return (
    <ConsoleShell title="Reconciliation" mode={status?.mode}>
      <div className="ph">
        <div>
          <h1>Outbox</h1>
          <p className="sub">
            Pending delivery events. Full reconciliation checks are not wired yet —
            use Dispatch pending to flush the local outbox.
          </p>
        </div>
        <DispatchButton />
      </div>
      <section className="card">
        <div className="ch">
          <h2>Outbox</h2>
          <span className="pill">
            <span className="dot" style={{ background: "var(--amber)" }} />
            {outbox?.pending ?? "—"} pending
          </span>
        </div>
        <table className="table">
          <thead>
            <tr>
              <th>Event</th>
              <th>Subject</th>
              <th>Seq</th>
            </tr>
          </thead>
          <tbody>
            {(outbox?.items || []).map((i) => (
              <tr key={i.outbox_id}>
                <td>{i.event_type}</td>
                <td className="mono">{i.subject_id.slice(0, 12)}…</td>
                <td>{i.sequence}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </ConsoleShell>
  );
}
