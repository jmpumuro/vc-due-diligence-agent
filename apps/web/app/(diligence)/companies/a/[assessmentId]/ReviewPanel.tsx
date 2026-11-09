"use client";

import { useState } from "react";
import {
  postReviewDecision,
  type ReviewDecision,
  type ReviewTarget,
} from "@/lib/review-api";
import { decisionActionCopy, errorCopy } from "@/lib/status-copy";

export default function ReviewPanel({
  apiBase,
  assessmentId,
  revision,
  target,
  state,
  draftRequests = [],
}: {
  apiBase: string;
  assessmentId: string;
  revision: number;
  target: ReviewTarget | null;
  state: string;
  draftRequests?: string[];
}) {
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const seeded =
    draftRequests.map((s) => s.trim()).filter(Boolean).slice(0, 8).join("\n") ||
    "Confirm primary-source evidence for open workstream gaps";
  const [infoItems, setInfoItems] = useState(seeded);

  if (state !== "AWAITING_REVIEW" || !target) {
    return null;
  }

  const reviewTarget = target;

  async function decide(decision: ReviewDecision) {
    setBusy(true);
    setMessage(null);
    try {
      const requested_items =
        decision === "request_information"
          ? infoItems
              .split("\n")
              .map((s) => s.trim())
              .filter(Boolean)
          : [];
      if (decision === "request_information" && !requested_items.length) {
        setMessage("Add at least one information request item.");
        setBusy(false);
        return;
      }
      const comment =
        decision === "approve"
          ? "Approved from Thesis UI"
          : decision === "reject"
            ? "Rejected from Thesis UI"
            : decision === "request_research"
              ? "Request additional research"
              : "Information requested from Thesis UI";
      const result = await postReviewDecision({
        apiBase,
        assessmentId,
        revision,
        target: reviewTarget,
        decision,
        comment,
        requestedItems: requested_items,
        idempotencyPrefix: "ui",
      });
      if (!result.ok) {
        setMessage(
          `Review failed (${result.status}): ${errorCopy[result.detail] || result.detail}`,
        );
        return;
      }
      setMessage(`Decision recorded: ${decision}`);
      window.location.reload();
    } catch (e) {
      setMessage(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card">
      <div className="ch">
        <h2>Human review</h2>
        <span className="pill">
          <span className="dot" style={{ background: "var(--amber)" }} />
          Revision {revision}
        </span>
      </div>
      <div className="cb stack">
        <p className="mute" style={{ margin: 0 }}>
          Version-bound approval. Concurrent decides return 409 REVIEW_ALREADY_DECIDED; digest
          mismatch returns STALE_REVIEW_TARGET.
        </p>
        <label className="stack" style={{ gap: 4 }}>
          <span className="lbl">Information request items (one per line)</span>
          <textarea
            className="input"
            value={infoItems}
            onChange={(e) => setInfoItems(e.target.value)}
            rows={3}
          />
        </label>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
          <button className="btn btn-primary" type="button" disabled={busy} onClick={() => decide("approve")}>
            {decisionActionCopy.approve}
          </button>
          <button className="btn" type="button" disabled={busy} onClick={() => decide("reject")}>
            {decisionActionCopy.reject}
          </button>
          <button
            className="btn"
            type="button"
            disabled={busy}
            onClick={() => decide("request_information")}
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
        </div>
        {message && (
          <p className={message.startsWith("Review failed") || message.startsWith("Add") ? "err" : "mute"}>
            {message}
          </p>
        )}
      </div>
    </section>
  );
}
