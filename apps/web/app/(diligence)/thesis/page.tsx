import Link from "next/link";
import ResearchShell from "@/components/shell/ResearchShell";

const MANDATE = {
  thesis:
    "B2B software and infrastructure that decarbonises energy, industry and logistics, sold to regulated or asset-heavy buyers in Europe and North America.",
  fields: [
    { label: "Stages", value: "Seed → Series A" },
    { label: "Check size", value: "€0.5–3M" },
    { label: "Geography", value: "Europe + North America" },
    { label: "Exclusions", value: "Consumer social, pure hardware manufacturing" },
    { label: "Advance line", value: "Attractiveness ≥ 3.5 with no critical open risks" },
  ],
};

const RUBRIC = [
  { name: "Problem severity", weight: 20, anchor: "Must-have for regulated or asset-heavy buyers" },
  { name: "Solution fit", weight: 20, anchor: "Clear wedge into an existing workflow" },
  { name: "Team", weight: 20, anchor: "Domain depth + shipping velocity" },
  { name: "Traction", weight: 20, anchor: "Evidence of repeatable demand" },
  { name: "Thesis alignment", weight: 20, anchor: "Decarbonisation + B2B infrastructure" },
];

export default function ThesisPage() {
  return (
    <ResearchShell title="Investment thesis" crumbs={["Investment thesis"]} demo>
      <div className="ph">
        <div>
          <h1>Investment thesis</h1>
          <p className="sub">
            What the agents look for. Changes apply to new research; reviews already running keep
            their version.
          </p>
        </div>
        <span className="chip" title="Thesis edits apply when the write API ships">
          Read-only
        </span>
      </div>

      <section className="card">
        <div className="ch">
          <h2>Mandate</h2>
          <span className="chip">Read-only</span>
        </div>
        <div className="cb stack">
          <label className="lbl" style={{ display: "flex", flexDirection: "column", gap: 6, fontWeight: 500 }}>
            Thesis
            <textarea
              className="input"
              readOnly
              style={{ minHeight: 84, padding: 12, resize: "vertical", fontSize: 15, lineHeight: 1.6 }}
              value={MANDATE.thesis}
            />
          </label>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 16 }}>
            {MANDATE.fields.map((m) => (
              <div key={m.label} style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                <span className="lbl" style={{ fontWeight: 500 }}>
                  {m.label}
                </span>
                <input className="input" readOnly value={m.value} />
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="card">
        <div className="ch">
          <h2>How companies are scored</h2>
          <span className="lbl">Weights total 100%</span>
        </div>
        {RUBRIC.map((r) => (
          <div
            key={r.name}
            className="li"
            style={{ display: "flex", flexWrap: "wrap", gap: "8px 16px", alignItems: "center" }}
          >
            <span style={{ flex: "1 1 140px", fontWeight: 600 }}>{r.name}</span>
            <span className="lbl" style={{ flex: "3 1 300px" }}>
              {r.anchor}
            </span>
            <span className="bar" style={{ flex: "1 1 100px" }}>
              <span style={{ display: "block", height: "100%", width: `${r.weight * 5}%`, background: "var(--brand)" }} />
            </span>
            <span style={{ width: 44, textAlign: "right", fontWeight: 600 }}>{r.weight}%</span>
          </div>
        ))}
      </section>

      <p className="lbl" style={{ margin: 0 }}>
        Which diligence domains run at each level is set in <Link href="/settings">Settings</Link>.
        Agent routes, spending limits and source settings are managed in the{" "}
        <Link href="/console">agent console</Link>. Versioned writes land via{" "}
        <code className="mono">POST /config/versions</code>.
      </p>
    </ResearchShell>
  );
}
