import StatusPill from "@/components/ui/StatusPill";
import { recBlurb, recLabel, stateLabel } from "@/lib/status-copy";

export default function VerdictStrip({
  recommendation,
  conditions,
  headline,
  level,
  state,
}: {
  recommendation?: string | null;
  conditions?: string[];
  headline?: string | null;
  level: number;
  state: string;
}) {
  const rec = recLabel(recommendation);
  const withConditions = recommendation === "advance" && !!conditions?.length;
  return (
    <section className="card">
      <div className="ch">
        <h2>Partner call (suggested)</h2>
        <StatusPill color="var(--brand)">
          L{level} · {stateLabel(state)}
        </StatusPill>
      </div>
      <div className="cb verdict" style={{ paddingTop: 12 }}>
        <div className="rec">{withConditions ? "Advance, with conditions" : rec}</div>
        <p className="mute flush" style={{ marginTop: 4, maxWidth: 640 }}>
          {recBlurb(recommendation)} Agents assist; the investment decision stays with partners.
        </p>
        {headline && (
          <p className="lede" style={{ marginTop: 12 }}>
            {headline}
          </p>
        )}
        {!!conditions?.length && (
          <div style={{ marginTop: 12 }}>
            <div className="lbl">Conditions before commit</div>
            <ul className="stack list-cond" style={{ marginTop: 6 }}>
              {conditions.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </section>
  );
}
