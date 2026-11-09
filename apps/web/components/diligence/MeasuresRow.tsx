type Measures = {
  source_reliability?: { label?: string; independent_share?: string };
  claim_confidence?: { label?: string; verified?: number; source_supported?: number };
  evidence_coverage?: {
    domains_sufficient?: number;
    domains_partial?: number;
    domains_insufficient?: number;
  };
  attractiveness?: { score?: string; range?: string[]; advance_threshold?: string };
};

export default function MeasuresRow({ measures }: { measures?: Measures | null }) {
  if (!measures) {
    return (
      <section className="card">
        <div className="ch">
          <h2>Screen scorecard</h2>
        </div>
        <div className="cb">
          <p className="mute" style={{ margin: 0 }}>
            Scorecard fills in once research posts a summary.
          </p>
        </div>
      </section>
    );
  }
  const cov = measures.evidence_coverage;
  const sufficient = cov?.domains_sufficient ?? 0;
  const partial = cov?.domains_partial ?? 0;
  const insufficient = cov?.domains_insufficient ?? 0;
  const scoped = Math.max(1, sufficient + partial + insufficient);
  const attr = measures.attractiveness;
  return (
    <section className="card">
      <div className="ch">
        <h2>Screen scorecard</h2>
        <span className="lbl">Public evidence quality · not a valuation</span>
      </div>
      <div className="measures">
        <div className="measure">
          <div className="m-label">Source quality</div>
          <div className="m-value">{measures.source_reliability?.label || "—"}</div>
          <div className="mute">
            Independent share {measures.source_reliability?.independent_share ?? "—"}
          </div>
        </div>
        <div className="measure">
          <div className="m-label">Finding confidence</div>
          <div className="m-value">{measures.claim_confidence?.label || "—"}</div>
          <div className="mute">
            {measures.claim_confidence?.verified ?? 0} partner-verified ·{" "}
            {measures.claim_confidence?.source_supported ?? 0} source-backed
          </div>
        </div>
        <div className="measure">
          <div className="m-label">Workstreams cleared</div>
          <div className="m-value">
            {sufficient} / {scoped}
          </div>
          <div className="bar">
            <span style={{ width: `${(sufficient / scoped) * 100}%` }} />
          </div>
          <div className="mute">
            {partial} need more · {insufficient} open gaps
          </div>
        </div>
        <div className="measure">
          <div className="m-label">Attractiveness (screen)</div>
          <div className="m-value">{attr?.score ?? "—"}</div>
          <div className="mute">
            Advance bar {attr?.advance_threshold ?? "—"}
            {attr?.range ? ` · scale ${attr.range.join("–")}` : ""}
          </div>
        </div>
      </div>
    </section>
  );
}
