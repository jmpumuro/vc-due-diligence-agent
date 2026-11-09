"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import ResearchShell from "@/components/shell/ResearchShell";
import { publicApiBase } from "@/lib/api";
import { ensureDemoSession } from "@/lib/demo-session";
import { errorCopy } from "@/lib/status-copy";

const LEVELS = [
  {
    n: 1,
    label: "Initial screening",
    hint: "Public sources · 5 of 12 domains",
    domains: "Company, team, market, product, thesis fit",
    sources: "Public web and filings",
    after: "Memo opens for partner review when domains finish",
  },
  {
    n: 2,
    label: "Public diligence",
    hint: "11 public domains (no private data room)",
    domains: "L1 plus competition, traction, capitalization, legal, security, governance",
    sources: "Public web, filings, news",
    after: "Full public report with open questions",
  },
  {
    n: 3,
    label: "Enhanced diligence",
    hint: "All 12 domains + data room · ClamAV uploads",
    domains: "All 12 domains including financials + data-room shell",
    sources: "Public research now · private PDFs via ClamAV + worker-docs parse",
    after: "Public L3 screen when OCR verified; private-doc agent stays off (D1)",
  },
];

export default function NewAssessmentPage() {
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [company, setCompany] = useState("");
  const [website, setWebsite] = useState("");
  const [level, setLevel] = useState(1);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [l3Screening, setL3Screening] = useState(false);
  const api = publicApiBase();

  const selected = useMemo(() => LEVELS.find((l) => l.n === level) || LEVELS[0], [level]);

  useEffect(() => {
    void loadPipeline();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function loadPipeline() {
    try {
      const res = await fetch(`${api}/api/v1/system/status`, { cache: "no-store" });
      if (!res.ok) return;
      const body = await res.json();
      setL3Screening(Boolean(body?.private_pipeline?.level3_screening));
    } catch {
      /* ignore */
    }
  }

  async function start() {
    setBusy(true);
    setMessage(null);
    try {
      await ensureDemoSession(api);
      await loadPipeline();
      const res = await fetch(`${api}/api/v1/assessments`, {
        method: "POST",
        credentials: "include",
        headers: {
          "content-type": "application/json",
          "Idempotency-Key": crypto.randomUUID(),
        },
        body: JSON.stringify({
          company_name: company.trim(),
          level,
          website: website.trim() || undefined,
          // L1/L2 always screen. L3 screens when OCR_PRODUCT_VERIFIED; else shell only.
          start_screening: level <= 2 || l3Screening,
        }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        const detail = String(body.detail || res.status);
        setMessage(errorCopy[detail] || `Failed: ${detail}`);
        return;
      }
      window.location.href = `/companies/a/${body.assessment_id}`;
    } catch (err) {
      setMessage(String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <ResearchShell title="New diligence" crumbs={["Companies", "New diligence"]}>
      <div className="wiz">
      <div className="ph">
        <div>
          <h1>New diligence</h1>
          <p className="sub">Three short steps. You can go deeper later without losing any work.</p>
        </div>
      </div>
      <div className="stepper" aria-label="Progress">
        {[
          { n: 1, label: "Company" },
          { n: 2, label: "Depth" },
          { n: 3, label: "Review" },
        ].map((s, i) => (
          <span key={s.n} style={{ display: "contents" }}>
            {i > 0 ? <span className={`sline${step > s.n - 1 ? " done" : ""}`} /> : null}
            <button
              type="button"
              className={`step${step === s.n ? " cur" : ""}${step > s.n ? " done" : ""}`}
              onClick={() => step > s.n && setStep(s.n as 1 | 2 | 3)}
            >
              <span className="n">{step > s.n ? "✓" : s.n}</span>
              {s.label}
            </button>
          </span>
        ))}
      </div>

      {step === 1 && (
        <section className="card">
          <div className="ch">
            <h2>Which company?</h2>
            <span className="lbl">We check for duplicates and similar names before starting</span>
          </div>
          <div className="cb stack">
            <div style={{ display: "flex", flexWrap: "wrap", gap: 12 }}>
              <label className="lbl" style={{ flex: "2 1 240px", display: "flex", flexDirection: "column", gap: 6, fontWeight: 500, color: "var(--text)" }}>
                Company name
                <input
                  className="input"
                  placeholder="Try Lattice, Kestrel or any new name"
                  value={company}
                  onChange={(e) => setCompany(e.target.value)}
                  required
                />
              </label>
              <label className="lbl" style={{ flex: "2 1 220px", display: "flex", flexDirection: "column", gap: 6, fontWeight: 500, color: "var(--text)" }}>
                Website (optional)
                <input
                  className="input"
                  placeholder="example.com"
                  value={website}
                  onChange={(e) => setWebsite(e.target.value)}
                />
              </label>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12, paddingTop: 8, borderTop: "1px solid var(--border)" }}>
              <Link className="btn btn-ghost" href="/">
                Cancel
              </Link>
              <button
                className="btn btn-primary"
                type="button"
                disabled={!company.trim()}
                onClick={() => setStep(2)}
              >
                Continue
              </button>
            </div>
          </div>
        </section>
      )}

      {step === 2 && (
        <section className="card">
          <div className="ch">
            <h2>How deep should we go?</h2>
            <span className="lbl">{company.trim()}</span>
          </div>
          <div className="cb stack">
            {LEVELS.map((l) => (
              <button
                key={l.n}
                type="button"
                className={`choice${level === l.n ? " on" : ""}`}
                style={{ flexDirection: "row", alignItems: "center", gap: 16 }}
                aria-pressed={level === l.n}
                onClick={() => setLevel(l.n)}
              >
                <span className="lvl" style={{ flex: "none" }}>
                  L{l.n}
                </span>
                <span style={{ flex: 1, display: "flex", flexDirection: "column", gap: 2 }}>
                  <span style={{ fontWeight: 600 }}>{l.label}</span>
                  <span className="lbl">{l.hint}</span>
                </span>
              </button>
            ))}
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12, paddingTop: 8, borderTop: "1px solid var(--border)" }}>
              <button className="btn btn-ghost" type="button" onClick={() => setStep(1)}>
                Back
              </button>
              <button className="btn btn-primary" type="button" onClick={() => setStep(3)}>
                Continue
              </button>
            </div>
          </div>
        </section>
      )}

      {step === 3 && (
        <section className="card">
          <div className="ch">
            <h2>Review and start</h2>
          </div>
          <div className="cb stack">
            <div className="kv" style={{ fontSize: 14, display: "grid", gridTemplateColumns: "160px 1fr", gap: "8px 16px" }}>
              <span className="mute">Company</span>
              <span style={{ fontWeight: 600 }}>{company.trim()}</span>
              <span className="mute">Website</span>
              <span>{website.trim() || "—"}</span>
              <span className="mute">Level</span>
              <span>
                L{selected.n} — {selected.label}
              </span>
              <span className="mute">Domains checked</span>
              <span>{selected.domains}</span>
              <span className="mute">Sources</span>
              <span>{selected.sources}</span>
              <span className="mute">After it starts</span>
              <span>{selected.after}</span>
            </div>
            {level === 3 && (
              <div className="callout" style={{ borderColor: "var(--amber)" }}>
                <strong style={{ fontWeight: 600 }}>
                  {l3Screening ? "L3 public screen ready" : "L3 shell · screening gated"}
                </strong>
                <span className="mute">
                  {" "}
                  {l3Screening
                    ? "Starts all 12 domains from public sources and opens the data room. Uploads are ClamAV-gated; OCR/parse via worker-docs. Private-document agent analysis stays off (D1)."
                    : "Creates the data-room shell now. Uploads work when ClamAV is healthy. Flip OCR_PRODUCT_VERIFIED after D4 smoke to enable L3 public screening. Private-document agent analysis stays off (D1)."}
                </span>
              </div>
            )}
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12, paddingTop: 8, borderTop: "1px solid var(--border)" }}>
              <button className="btn btn-ghost" type="button" onClick={() => setStep(2)} disabled={busy}>
                Back
              </button>
              <button className="btn btn-primary" type="button" disabled={busy} onClick={start}>
                {busy ? "Starting…" : "Start diligence"}
              </button>
            </div>
            {message && <p className="err">{message}</p>}
          </div>
        </section>
      )}
      </div>
    </ResearchShell>
  );
}
