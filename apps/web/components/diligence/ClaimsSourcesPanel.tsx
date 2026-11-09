"use client";

import { useMemo, useState } from "react";
import { ensureDemoSession } from "@/lib/demo-session";
import { domainMeta, trustLabel, verificationLabel } from "@/lib/status-copy";

export type ClaimRow = {
  claim_id: string;
  domain_id: string;
  statement: string;
  trust_state: string;
  verification_status: string;
  confidence?: number | string | null;
  evidence_quality?: string | null;
  claim_type?: string | null;
  company_authored?: boolean;
  source_urls?: string[];
  snapshot_ids?: string[];
  evidence_span_ids?: string[];
  numeric_facts?: string[];
  numeric_facts_grounded?: string[];
};

const KIND_FILTERS: Record<string, (c: ClaimRow) => boolean> = {
  verified: (c) => c.verification_status === "verified",
  supported: (c) => c.trust_state === "supported",
  inference: (c) => c.trust_state === "unsupported",
  missing: (c) => c.trust_state === "insufficient" || c.verification_status === "insufficient",
  contra: (c) => c.trust_state === "contested" || c.verification_status === "contested",
  calc: (c) => {
    const t = (c.claim_type || "").toLowerCase();
    return (
      t.includes("calc") ||
      t.includes("metric") ||
      t.includes("financial") ||
      (Array.isArray(c.numeric_facts) && c.numeric_facts.length > 0)
    );
  },
};

function hostLabel(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url.slice(0, 40);
  }
}

export default function ClaimsSourcesPanel({
  apiBase,
  items,
  kind,
}: {
  apiBase: string;
  items: ClaimRow[];
  kind?: string;
}) {
  const [rows, setRows] = useState(items);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const filtered = useMemo(() => {
    if (!kind || !(kind in KIND_FILTERS)) return rows;
    return rows.filter(KIND_FILTERS[kind]);
  }, [rows, kind]);

  async function setVerification(
    claim: ClaimRow,
    verification_status: "verified" | "contested" | "rejected" | "insufficient",
    trust_state?: ClaimRow["trust_state"],
  ) {
    setBusyId(claim.claim_id);
    setMessage(null);
    try {
      await ensureDemoSession(apiBase);
      const res = await fetch(`${apiBase}/api/v1/claims/${claim.claim_id}/verification`, {
        method: "PATCH",
        credentials: "include",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          verification_status,
          trust_state:
            trust_state ||
            (verification_status === "verified"
              ? "supported"
              : verification_status === "contested"
                ? "contested"
                : verification_status === "insufficient"
                  ? "insufficient"
                  : "unsupported"),
        }),
      });
      if (!res.ok) {
        setMessage(`Verification failed (${res.status}): ${await res.text()}`);
        return;
      }
      const updated = (await res.json()) as ClaimRow;
      setRows((prev) =>
        prev.map((r) => (r.claim_id === updated.claim_id ? { ...r, ...updated } : r)),
      );
      setMessage(`Updated ${updated.claim_id.slice(0, 8)}… → ${updated.verification_status}`);
    } catch (e) {
      setMessage(String(e));
    } finally {
      setBusyId(null);
    }
  }

  const kindLabel: Record<string, string> = {
    verified: "partner-verified",
    supported: "source-backed",
    inference: "inference",
    missing: "not evidenced",
    contra: "contested",
    calc: "calculated",
    risk: "risk",
  };

  return (
    <section className="card">
      <div className="ch">
        <h2>Findings & sources</h2>
        <span className="lbl">
          {filtered.length}
          {kind ? ` · ${kindLabel[kind] || kind}` : ""} of {rows.length} · cite before you rely
        </span>
      </div>
      <div className="cb">
        <p className="mute" style={{ margin: 0 }}>
          Each row is a diligence finding with the public pages behind it. Partner actions
          (Verify / Contest) stay on the firm — agents never decide.
        </p>
      </div>
      {!filtered.length ? (
        <div className="cb">
          <p className="mute" style={{ margin: 0 }}>
            {rows.length
              ? `No findings match “${kindLabel[kind || ""] || kind}”.`
              : "No findings posted yet for this screen."}
          </p>
        </div>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Workstream</th>
              <th>Finding</th>
              <th>Standing</th>
              <th>Evidence</th>
              <th>Cited pages</th>
              <th>Partner actions</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((c) => {
              const urls = (c.source_urls || []).filter(
                (u) => typeof u === "string" && u.startsWith("http") && !u.endsWith("/mirror"),
              );
              const conf =
                c.confidence == null || c.confidence === ""
                  ? null
                  : Number(c.confidence);
              const meta = domainMeta(c.domain_id);
              return (
                <tr key={c.claim_id}>
                  <td>
                    <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                      <span>{meta.name}</span>
                      <span className="lbl">
                        {c.claim_type || "fact"}
                        {c.company_authored ? " · company-authored" : ""}
                      </span>
                    </div>
                  </td>
                  <td>
                    <div style={{ display: "flex", flexDirection: "column", gap: 4, maxWidth: 420 }}>
                      <span>{c.statement}</span>
                      {Array.isArray(c.numeric_facts) && c.numeric_facts.length ? (
                        <span className="lbl">
                          Numbers claimed: {c.numeric_facts.join(", ")}
                          {Array.isArray(c.numeric_facts_grounded) &&
                          c.numeric_facts_grounded.length
                            ? ` · on page: ${c.numeric_facts_grounded.join(", ")}`
                            : ""}
                        </span>
                      ) : null}
                    </div>
                  </td>
                  <td>
                    <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                      <span>{trustLabel(c.trust_state)}</span>
                      <span className="lbl">{verificationLabel(c.verification_status)}</span>
                      {conf != null && !Number.isNaN(conf) ? (
                        <span className="lbl">{(conf * 100).toFixed(0)}% confidence</span>
                      ) : null}
                    </div>
                  </td>
                  <td>
                    <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                      <span>{c.evidence_quality || "—"}</span>
                      <span className="lbl">
                        {(c.snapshot_ids || []).length} snapshots ·{" "}
                        {(c.evidence_span_ids || []).length} quotes
                      </span>
                    </div>
                  </td>
                  <td>
                    {!urls.length ? (
                      <span className="mute">—</span>
                    ) : (
                      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                        {urls.map((u) => (
                          <a
                            key={u}
                            className="mono"
                            style={{ fontSize: 12 }}
                            href={u}
                            target="_blank"
                            rel="noreferrer"
                            title={u}
                          >
                            {hostLabel(u)}
                          </a>
                        ))}
                      </div>
                    )}
                  </td>
                  <td>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                      <button
                        type="button"
                        className="btn btn-sm"
                        disabled={busyId === c.claim_id || c.verification_status === "verified"}
                        onClick={() => setVerification(c, "verified", "supported")}
                      >
                        Mark verified
                      </button>
                      <button
                        type="button"
                        className="btn btn-sm"
                        disabled={busyId === c.claim_id}
                        onClick={() => setVerification(c, "contested", "contested")}
                      >
                        Contest
                      </button>
                      <button
                        type="button"
                        className="btn btn-sm"
                        disabled={busyId === c.claim_id}
                        onClick={() => setVerification(c, "insufficient", "insufficient")}
                      >
                        Not evidenced
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
      {message ? (
        <div className="cb">
          <p className={message.includes("failed") ? "err" : "mute"}>{message}</p>
        </div>
      ) : null}
    </section>
  );
}
