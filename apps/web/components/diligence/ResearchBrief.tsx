import Link from "next/link";
import StatusPill from "@/components/ui/StatusPill";
import { gateColor } from "@/lib/format";
import { domainMeta, gateLabel, recBlurb, recLabel } from "@/lib/status-copy";

type GateMap = Record<string, string>;

export default function ResearchBrief({
  assessmentId,
  recommendation,
  domainGates,
  claimTotal,
  contradictionTotal,
  llmUsed,
  sourceHosts,
}: {
  assessmentId: string;
  recommendation?: string | null;
  domainGates: GateMap;
  claimTotal: number;
  contradictionTotal: number;
  llmUsed: boolean;
  sourceHosts: string[];
}) {
  const entries = Object.entries(domainGates);
  const cleared = entries.filter(([, g]) => g === "sufficient").length;
  const needsMore = entries.filter(([, g]) => g === "partial").length;
  const openGaps = entries.filter(([, g]) => g === "insufficient").length;
  const gapDomains = entries
    .filter(([, g]) => g === "insufficient" || g === "partial")
    .map(([id]) => domainMeta(id).name);

  const pressy = sourceHosts.filter(
    (h) =>
      !h.includes("wikipedia") &&
      !h.includes("crunchbase") &&
      !h.includes("wikidata"),
  );

  return (
    <section className="card">
      <div className="ch">
        <h2>How this screen was researched</h2>
        <span className="lbl">Public web only · partner still decides</span>
      </div>
      <div className="cb stack-tight">
        <p className="flush" style={{ maxWidth: 720 }}>
          Agents ran a bounded public-web diligence pass
          {llmUsed ? " with agent reading of fetched pages" : ""} across the Level workstreams.
          Findings below cite independent pages where available — this is a screen, not a legal
          opinion or investment recommendation.
        </p>
        <div className="stat-grid">
          <div>
            <div className="lbl">Partner suggestion</div>
            <div className="v">{recLabel(recommendation)}</div>
            <div className="mute mute-sm">{recBlurb(recommendation)}</div>
          </div>
          <div>
            <div className="lbl">Workstreams cleared</div>
            <div className="v">
              {cleared} / {entries.length || "—"}
            </div>
            <div className="mute mute-sm">
              {needsMore} need more · {openGaps} open gaps
            </div>
          </div>
          <div>
            <div className="lbl">Findings on file</div>
            <div className="v">{claimTotal}</div>
            <div className="mute mute-sm">{contradictionTotal} contested</div>
          </div>
          <div>
            <div className="lbl">Independent sources</div>
            <div className="v">{pressy.length || sourceHosts.length}</div>
            <div className="mute mute-sm">
              {(pressy.length ? pressy : sourceHosts).slice(0, 4).join(" · ") || "—"}
              {(pressy.length ? pressy : sourceHosts).length > 4 ? "…" : ""}
            </div>
          </div>
        </div>
        {gapDomains.length ? (
          <div>
            <div className="lbl">Partner follow-ups</div>
            <p className="mute mute-sm flush" style={{ marginTop: 4 }}>
              Still thin on {gapDomains.join(", ")}. Review{" "}
              <Link href={`/companies/a/${assessmentId}?tab=domains`}>workstreams</Link> or{" "}
              <Link href={`/companies/a/${assessmentId}?tab=sources&kind=missing`}>
                not-evidenced findings
              </Link>
              .
            </p>
          </div>
        ) : (
          <p className="mute mute-sm flush">
            No open workstream gaps on this level — still confirm anything material before a
            commit.
          </p>
        )}
        {entries.length ? (
          <div className="hstack-wrap">
            {entries.map(([id, gate]) => (
              <StatusPill key={id} color={gateColor(gate)} title={gate}>
                {domainMeta(id).name}: {gateLabel(gate)}
              </StatusPill>
            ))}
          </div>
        ) : null}
      </div>
    </section>
  );
}
