"use client";

import { useEffect, useState } from "react";
import { publicApiBase } from "@/lib/api";

type Match = {
  subject: string;
  matched_name?: string;
  band?: string;
  review_status?: string;
  score?: number;
  programs?: string[];
};

type DatasetMeta = {
  source?: string;
  source_url?: string;
  dataset?: string;
  label?: string;
  mode?: string;
  list_uid?: string;
  entry_count?: number;
  record_count?: number;
  disclaimer?: string;
};

export default function SanctionsCard({ companyName }: { companyName: string }) {
  const [dataset, setDataset] = useState<DatasetMeta>({ label: "OFAC SDN" });
  const [matches, setMatches] = useState<Match[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [screened, setScreened] = useState(false);
  const api = publicApiBase();

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const ds = await fetch(`${api}/api/v1/sanctions/dataset?prefer_live=true`, {
          credentials: "include",
        });
        if (ds.ok) {
          const body = (await ds.json()) as DatasetMeta;
          if (!cancelled) setDataset(body);
        }
      } catch {
        /* ignore */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [api]);

  async function screen() {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${api}/api/v1/sanctions/screen`, {
        method: "POST",
        credentials: "include",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ subjects: [companyName], prefer_live: true }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(String(body.detail || res.status));
        return;
      }
      if (body.dataset) {
        setDataset(body.dataset as DatasetMeta);
      }
      const items = (body.potential_matches || []) as Match[];
      setMatches(items);
      setScreened(true);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  const label =
    dataset.source || dataset.dataset || dataset.label || dataset.source_url || "OFAC SDN";
  const mode = dataset.mode || "unknown";
  const count =
    typeof dataset.record_count === "number"
      ? dataset.record_count
      : typeof dataset.entry_count === "number"
        ? dataset.entry_count
        : null;

  return (
    <section className="card" style={{ marginTop: 16 }}>
      <div className="ch">
        <h2>Sanctions screening</h2>
        <span className="lbl">
          {label}
          {mode ? ` · ${mode}` : ""}
          {count != null ? ` · ${count} entries` : ""}
        </span>
      </div>
      <div className="cb lbl">
        {dataset.disclaimer ||
          "Subjects screened against OFAC. Informational diligence aid, not a substitute for professional compliance review. Matches are potential-only — never auto-declared sanctioned."}
        {dataset.list_uid ? ` List ${dataset.list_uid}.` : ""}
      </div>
      {!screened ? (
        <div className="cb" style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
          <button type="button" className="btn btn-sm" disabled={busy} onClick={screen}>
            {busy ? "Screening…" : `Screen “${companyName}”`}
          </button>
          {error ? <span className="err">{error}</span> : null}
        </div>
      ) : !matches.length ? (
        <div className="cb" style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
          <span className="pill" style={{ ["--c" as string]: "var(--green)" }}>
            <span className="dot" style={{ background: "var(--green)" }} />
            No potential matches
          </span>
          <button type="button" className="btn btn-sm btn-ghost" disabled={busy} onClick={screen}>
            Re-screen
          </button>
          {error ? <span className="err">{error}</span> : null}
        </div>
      ) : (
        <>
          {matches.map((m, i) => (
            <div
              key={`${m.subject}-${i}`}
              className="li"
              style={{ display: "flex", flexWrap: "wrap", gap: "8px 16px", alignItems: "center" }}
            >
              <span className="pill" style={{ ["--c" as string]: "var(--amber)" }}>
                <span className="dot" style={{ background: "var(--amber)" }} />
                Potential match: requires human review
              </span>
              <span style={{ flex: "1 1 320px", display: "flex", flexDirection: "column", gap: 2 }}>
                <span style={{ fontWeight: 500 }}>{m.subject}</span>
                <span className="lbl">
                  List entry: {m.matched_name || "—"} · {m.band || "band n/a"}
                  {m.score != null ? ` · score ${m.score}` : ""}
                </span>
                <span className="lbl">
                  {m.review_status || "needs_review"}
                  {Array.isArray(m.programs) && m.programs.length
                    ? ` · ${m.programs.join(", ")}`
                    : ""}
                </span>
              </span>
            </div>
          ))}
          <div className="cb">
            <button type="button" className="btn btn-sm btn-ghost" disabled={busy} onClick={screen}>
              Re-screen
            </button>
            {error ? <span className="err">{error}</span> : null}
          </div>
        </>
      )}
    </section>
  );
}
