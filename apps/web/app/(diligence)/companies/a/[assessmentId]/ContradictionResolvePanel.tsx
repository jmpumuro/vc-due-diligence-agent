"use client";

import { useState } from "react";
import { ensureDemoSession } from "@/lib/demo-session";

type Contradiction = {
  contradiction_id: string;
  severity: string;
  contradiction_type: string;
  explanation: string;
  resolution: string;
  version: number;
  human_review_state?: string;
  domain_ids?: string[];
  claim_ids?: string[];
  evidence_for?: string[];
  evidence_against?: string[];
};

type Resolution = "accepted_risk" | "resolved_with_private" | "waived" | "open";

type HistoryItem = {
  resolution?: string;
  comment?: string | null;
  human_review_state?: string | null;
  created_at?: string | null;
  actor_user_id?: string | null;
};

export default function ContradictionResolvePanel({
  apiBase,
  items,
  claimLookup = {},
}: {
  apiBase: string;
  items: Contradiction[];
  claimLookup?: Record<string, string>;
}) {
  const [rows, setRows] = useState(items);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [comment, setComment] = useState("Resolved from Thesis UI");
  const [historyId, setHistoryId] = useState<string | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [historyBusy, setHistoryBusy] = useState(false);

  if (!rows.length) {
    return (
      <section className="card">
        <div className="ch">
          <h2>Contested findings</h2>
        </div>
        <div className="cb">
          <p className="mute" style={{ margin: 0 }}>
            No contested findings on this screen.
          </p>
        </div>
      </section>
    );
  }

  async function resolve(c: Contradiction, resolution: Resolution) {
    setBusyId(c.contradiction_id);
    setMessage(null);
    try {
      await ensureDemoSession(apiBase);
      const res = await fetch(`${apiBase}/api/v1/contradictions/${c.contradiction_id}/resolve`, {
        method: "POST",
        credentials: "include",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          expected_version: c.version,
          resolution,
          comment,
          human_review_state: "decided",
        }),
      });
      if (res.status === 409) {
        setMessage("VERSION_CONFLICT — refresh and retry with the current version.");
        return;
      }
      if (!res.ok) {
        setMessage(`Resolve failed (${res.status}): ${await res.text()}`);
        return;
      }
      const updated = (await res.json()) as Contradiction;
      setRows((prev) =>
        prev.map((row) => (row.contradiction_id === updated.contradiction_id ? { ...row, ...updated } : row)),
      );
      setMessage(
        `Resolved ${updated.contradiction_id.slice(0, 8)}… → ${updated.resolution} (v${updated.version})`,
      );
    } catch (e) {
      setMessage(String(e));
    } finally {
      setBusyId(null);
    }
  }

  async function loadHistory(c: Contradiction) {
    if (historyId === c.contradiction_id) {
      setHistoryId(null);
      setHistory([]);
      return;
    }
    setHistoryBusy(true);
    setHistoryId(c.contradiction_id);
    try {
      const res = await fetch(
        `${apiBase}/api/v1/contradictions/${c.contradiction_id}/history`,
        { credentials: "include" },
      );
      if (!res.ok) {
        setMessage(`History failed (${res.status})`);
        setHistory([]);
        return;
      }
      const body = (await res.json()) as { items?: HistoryItem[] };
      setHistory(body.items || []);
    } catch (e) {
      setMessage(String(e));
      setHistory([]);
    } finally {
      setHistoryBusy(false);
    }
  }

  return (
    <section className="card">
      <div className="ch">
        <h2>Contested findings</h2>
        <span className="lbl">{rows.length} need a partner call</span>
      </div>
      <div className="cb stack">
        <p className="mute" style={{ margin: 0 }}>
          Accept risk, resolve with private materials, or waive. Concurrent edits return a
          version conflict — refresh and retry.
        </p>
        <label className="stack" style={{ gap: 4 }}>
          <span className="lbl">Resolution comment</span>
          <input
            className="input"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
          />
        </label>
      </div>
      <table className="table">
        <thead>
          <tr>
            <th>Severity</th>
            <th>Domains / claims</th>
            <th>Explanation</th>
            <th>Resolution</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((c) => (
            <tr key={c.contradiction_id}>
              <td>
                <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                  <span>{c.severity}</span>
                  <span className="lbl">{c.contradiction_type}</span>
                  <span className="mono lbl">v{c.version}</span>
                </div>
              </td>
              <td>
                <div style={{ display: "flex", flexDirection: "column", gap: 4, maxWidth: 280 }}>
                  <span className="lbl">
                    {(c.domain_ids || []).length
                      ? (c.domain_ids || []).join(", ")
                      : "—"}
                  </span>
                  {(c.claim_ids || []).length ? (
                    <ul style={{ margin: 0, paddingLeft: 16 }}>
                      {(c.claim_ids || []).slice(0, 4).map((id) => (
                        <li key={id} className="lbl">
                          {claimLookup[id]
                            ? `${claimLookup[id].slice(0, 80)}${claimLookup[id].length > 80 ? "…" : ""}`
                            : `${id.slice(0, 8)}…`}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <span className="mute">No linked claims</span>
                  )}
                  <span className="lbl">
                    evidence {(c.evidence_for || []).length} for /{" "}
                    {(c.evidence_against || []).length} against
                  </span>
                </div>
              </td>
              <td>{c.explanation}</td>
              <td>
                <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                  <span>{c.resolution}</span>
                  <span className="lbl">{c.human_review_state || "—"}</span>
                </div>
              </td>
              <td>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                  <button
                    className="btn btn-sm"
                    type="button"
                    disabled={busyId === c.contradiction_id || c.resolution !== "open"}
                    onClick={() => resolve(c, "accepted_risk")}
                  >
                    Accept risk
                  </button>
                  <button
                    className="btn btn-sm"
                    type="button"
                    disabled={busyId === c.contradiction_id || c.resolution !== "open"}
                    onClick={() => resolve(c, "resolved_with_private")}
                  >
                    Private resolve
                  </button>
                  <button
                    className="btn btn-sm"
                    type="button"
                    disabled={busyId === c.contradiction_id || c.resolution !== "open"}
                    onClick={() => resolve(c, "waived")}
                  >
                    Waive
                  </button>
                  <button
                    className="btn btn-sm btn-ghost"
                    type="button"
                    disabled={historyBusy && historyId === c.contradiction_id}
                    onClick={() => loadHistory(c)}
                  >
                    {historyId === c.contradiction_id ? "Hide history" : "History"}
                  </button>
                </div>
                {historyId === c.contradiction_id ? (
                  <div style={{ marginTop: 8 }}>
                    {!history.length ? (
                      <span className="mute">
                        {historyBusy ? "Loading…" : "No resolution history."}
                      </span>
                    ) : (
                      <ul style={{ margin: 0, paddingLeft: 16 }}>
                        {history.map((h, i) => (
                          <li key={`${c.contradiction_id}-h-${i}`} className="lbl">
                            {h.created_at
                              ? new Date(h.created_at).toLocaleString("en-GB", {
                                  day: "numeric",
                                  month: "short",
                                  hour: "2-digit",
                                  minute: "2-digit",
                                })
                              : "—"}{" "}
                            · {h.resolution || "—"}
                            {h.comment ? ` — ${h.comment}` : ""}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                ) : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {message && (
        <div className="cb">
          <p className={message.includes("failed") || message.includes("CONFLICT") ? "err" : "mute"}>
            {message}
          </p>
        </div>
      )}
    </section>
  );
}
