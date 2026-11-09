import Link from "next/link";
import ResearchShell from "@/components/shell/ResearchShell";
import StatusPill from "@/components/ui/StatusPill";
import { apiJson } from "@/lib/api";
import { sessionCookie } from "@/lib/session";

export default async function SettingsPage() {
  const cookie = await sessionCookie();
  const status = cookie
    ? await apiJson<{
        mode?: string;
        provider?: { state?: string; model?: string };
        demo_workspace?: boolean;
      }>("/api/v1/system/status", cookie)
    : await apiJson<{
        mode?: string;
        provider?: { state?: string; model?: string };
        demo_workspace?: boolean;
      }>("/api/v1/system/status");

  const privateAiOff = true; // D1 default — private docs never go external until allowed
  const providerState = status?.provider?.state || "unknown";

  return (
    <ResearchShell
      title="Settings"
      crumbs={["Settings"]}
      demo={Boolean(status?.demo_workspace)}
      mode={String(status?.mode || "")}
    >
      <div className="ph">
        <div>
          <h1>Settings</h1>
          <p className="sub">
            Workspace rules for private documents and diligence domains. Changes apply to new
            assessments and revisions. Thesis is open source under Apache-2.0.
          </p>
        </div>
      </div>

      <section className="card">
        <div className="ch">
          <h2>External processing of private documents</h2>
          <StatusPill color={privateAiOff ? "var(--green)" : "var(--amber)"}>
            {privateAiOff ? "Off (default)" : "Allowed for selected kinds"}
          </StatusPill>
        </div>
        <div className="cb stack">
          <p className="flush" style={{ maxWidth: 760 }}>
            Off by default. Uploaded documents stay on this server. Agent analysis of private
            documents runs only on a local route you host, or on an external provider if a
            workspace owner or admin allows specific kinds of data below. Thesis is not tied to a
            single vendor — the server checks policy before every request.
          </p>
          <div className="kv dense">
            <span className="mute">Route for private data</span>
            <span>Local only · external blocked</span>
            <span className="mute">Local agent route</span>
            <span>Not registered (compose profile <code className="mono">local-llm</code>)</span>
            <span className="mute">Public screening agent</span>
            <span>
              {status?.provider?.model || "—"} · route {providerState}
            </span>
            <span className="mute">Readiness</span>
            <span>{String(status?.mode || "—")}</span>
          </div>
          <p className="lbl flush">
            Policy edits will call <code className="mono">PATCH /config/current</code> (D1) when the
            write path ships. Until then this panel is read-only.
          </p>
        </div>
      </section>

      <section className="card">
        <div className="ch">
          <h2>Diligence domains</h2>
          <span className="lbl">12 domains · level gates</span>
        </div>
        <div className="cb">
          <p className="mute flush">
            Which domains run at each level is defined server-side. Partners edit the mandate and
            rubric on <Link href="/thesis">Investment thesis</Link>.
          </p>
        </div>
      </section>

      <section className="card">
        <div className="ch">
          <h2>Data-room retention</h2>
          <span className="chip">D2 · read-only</span>
        </div>
        <div className="cb">
          <p className="mute flush">
            Retention scan workflow lists candidates only. Destructive delete and DeletionCertificate
            remain gated (REM retention).
          </p>
        </div>
      </section>

      <section className="card">
        <div className="ch">
          <h2>Notifications</h2>
        </div>
        <div className="cb">
          <p className="mute flush">
            In-app notifications arrive from the outbox. Optional webhook is configured on the API;
            SMTP is not shipped.
          </p>
        </div>
      </section>
    </ResearchShell>
  );
}
