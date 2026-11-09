"use client";

import Link from "next/link";

const KINDS = [
  { id: "verified", label: "Partner-verified", color: "var(--green)" },
  { id: "supported", label: "Source-backed", color: "var(--blue)" },
  { id: "calc", label: "Calculated metric", color: "var(--brand)" },
  { id: "inference", label: "Inference only", color: "var(--amber)" },
  { id: "contra", label: "Contested", color: "var(--red)" },
  { id: "missing", label: "Not evidenced", color: "var(--gray)" },
] as const;

type KindId = (typeof KINDS)[number]["id"];

function kindHref(assessmentId: string, kind: KindId): string {
  if (kind === "calc") return `/companies/a/${assessmentId}?tab=financials`;
  if (kind === "contra") return `/companies/a/${assessmentId}?tab=contradictions`;
  return `/companies/a/${assessmentId}?tab=sources&kind=${kind}`;
}

export default function FindingKindBar({
  assessmentId,
  counts,
}: {
  assessmentId: string;
  counts?: Partial<Record<KindId, number>>;
}) {
  const values = KINDS.map((k) => ({
    ...k,
    n: Math.max(0, counts?.[k.id] ?? 0),
  }));
  const total = values.reduce((s, v) => s + v.n, 0);
  if (!total) return null;

  return (
    <section className="card kind-bar">
      <div className="hstack-wrap" style={{ justifyContent: "space-between" }}>
        <h2>{total} findings on this screen</h2>
        <span className="lbl">Click a kind to open the matching view</span>
      </div>
      <div className="kind-track">
        {values
          .filter((v) => v.n > 0)
          .map((v) => (
            <Link
              key={v.id}
              href={kindHref(assessmentId, v.id)}
              className="kind-seg"
              aria-label={`${v.n} ${v.label}`}
              style={{ flex: `${v.n} 1 0`, background: v.color }}
            />
          ))}
      </div>
      <div className="kind-legend">
        {values.map((v) => (
          <Link key={v.id} href={kindHref(assessmentId, v.id)}>
            <span className="dot" style={{ background: v.color }} />
            <strong>{v.n}</strong>
            <span className="mute">{v.label}</span>
          </Link>
        ))}
      </div>
    </section>
  );
}
