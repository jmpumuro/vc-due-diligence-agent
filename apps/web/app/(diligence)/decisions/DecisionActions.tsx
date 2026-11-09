"use client";

import { useState } from "react";
import {
  postReviewDecision,
  type ReviewDecision,
  type ReviewTarget,
} from "@/lib/review-api";
import { decisionActionCopy, errorCopy } from "@/lib/status-copy";

export default function DecisionActions({
  apiBase,
  assessmentId,
  revision,
  target,
}: {
  apiBase: string;
  assessmentId: string;
  revision: number;
  target: ReviewTarget;
}) {
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [infoItems, setInfoItems] = useState("Missing incorporation docs\nConfirm ARR bridge");
  const [showInfo, setShowInfo] = useState(false);

  async function decide(decision: ReviewDecision) {
    setBusy(true);
    setMsg(null);
    try {
      const requestedItems =
        decision === "request_information"
          ? infoItems
              .split("\n")
              .map((s) => s.trim())
              .filter(Boolean)
          : [];
      if (decision === "request_information" && !requestedItems.length) {
        setMsg("Add at least one information request item.");
        setBusy(false);
        return;
      }
      const result = await postReviewDecision({
        apiBase,
        assessmentId,
        revision,
        target,
        decision,
        comment: `UI ${decision}`,
        requestedItems,
        idempotencyPrefix: "decisions",
      });
      if (!result.ok) {
        setMsg(errorCopy[result.detail] || result.detail);
        return;
      }
      window.location.reload();
    } catch (e) {
      setMsg(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
      <button
        className="btn btn-primary"
        type="button"
        disabled={busy}
        onClick={() => decide("approve")}
      >
        {decisionActionCopy.approve}
      </button>
      <button className="btn" type="button" disabled={busy} onClick={() => decide("reject")}>
        {decisionActionCopy.reject}
      </button>
      <button
        className="btn"
        type="button"
        disabled={busy}
        onClick={() => setShowInfo((v) => !v)}
      >
        {decisionActionCopy.request_information}
      </button>
      <button
        className="btn"
        type="button"
        disabled={busy}
        onClick={() => decide("request_research")}
      >
        {decisionActionCopy.request_research}
      </button>
      {showInfo ? (
        <div className="stack" style={{ flex: "1 1 100%", gap: 8 }}>
          <label className="stack" style={{ gap: 4 }}>
            <span className="lbl">Information request items (one per line)</span>
            <textarea
              className="input"
              value={infoItems}
              onChange={(e) => setInfoItems(e.target.value)}
              rows={3}
            />
          </label>
          <button
            className="btn btn-primary"
            type="button"
            disabled={busy}
            onClick={() => decide("request_information")}
          >
            Send information request
          </button>
        </div>
      ) : null}
      {msg ? <p className="err" style={{ margin: 0, flex: "1 1 100%" }}>{msg}</p> : null}
    </div>
  );
}
