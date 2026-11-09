import StatusPill from "@/components/ui/StatusPill";
import { workstreamDotColor } from "@/lib/format";
import { domainMeta, gateLabel } from "@/lib/status-copy";

type Domain = {
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
  can_retry?: boolean;
};

function workstreamStatus(status: string, gate: string) {
  if (status === "running" || status === "active") return "In research";
  if (status === "pending" || status === "queued") return "Queued";
  if (status === "skipped") return "Out of level";
  // Prefer gate once research has posted a result (complete/partial/done).
  if (gate === "sufficient") return "Cleared";
  if (gate === "partial") return "Needs more";
  if (gate === "insufficient") return "Open gap";
  if (gate === "unavailable_at_level") return "Out of level";
  if (status === "completed" || status === "complete" || status === "done") return "Done";
  return status;
}

export default function DomainTable({ domains }: { domains: Domain[] }) {
  const active = domains.filter((d) => d.gate_result !== "unavailable_at_level").length;
  const cleared = domains.filter((d) => d.gate_result === "sufficient").length;
  return (
    <section className="card">
      <div className="ch">
        <h2>Diligence workstreams</h2>
        <span className="lbl">
          {cleared} cleared · {active} in scope · {domains.length} total
        </span>
      </div>
      <div className="cb">
        <p className="mute flush">
          Each workstream is a partner question. “Cleared” means independent public sources support
          a finding; “Open gap” means it is not evidenced yet.
        </p>
      </div>
      <div className="scroll">
        <div className="domains-grid">
          <div className="thd domains-cols">
            <span>Workstream</span>
            <span>Status</span>
            <span>Diligence bar</span>
            <span>Source coverage</span>
            <span>Findings</span>
            <span>Contested</span>
            <span>Risks</span>
            <span>Asks</span>
          </div>
          {domains.map((d) => {
            const meta = domainMeta(d.domain_id);
            const pct = d.sources_required
              ? Math.min(100, (d.sources_found / d.sources_required) * 100)
              : 0;
            const tone = workstreamDotColor(d.status, d.gate_result);
            return (
              <div
                key={d.domain_id}
                className="tr domains-cols"
                style={{ cursor: "default" }}
              >
                <span className="vstack">
                  <span style={{ fontWeight: 600 }}>{meta.name}</span>
                  <span className="lbl">{meta.partnerAsk || meta.scope}</span>
                </span>
                <span>
                  <StatusPill color={tone}>
                    {workstreamStatus(d.status, d.gate_result)}
                  </StatusPill>
                </span>
                <span className="vstack">
                  <span>{gateLabel(d.gate_result)}</span>
                  {d.reason ? <span className="lbl">{d.reason}</span> : null}
                </span>
                <span className="vstack" style={{ gap: 4 }}>
                  <span className="bar">
                    <span
                      className="fill"
                      style={{ width: `${pct}%`, ["--c" as string]: tone }}
                    />
                  </span>
                  <span className="lbl">
                    {d.sources_found} independent · {d.sources_required} target
                  </span>
                </span>
                <span>{d.findings}</span>
                <span>{d.contradictions}</span>
                <span>{d.risks}</span>
                <span>{d.requests}</span>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
