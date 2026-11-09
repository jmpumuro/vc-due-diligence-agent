import { ensureDemoSession } from "@/lib/demo-session";

export type ReviewTarget = {
  assessment_id: string;
  assessment_revision: number;
  evidence_snapshot_id: string;
  evaluation_id: string;
  memo_version_id: string;
  review_policy_version: string;
};

export type ReviewDecision =
  | "approve"
  | "reject"
  | "request_information"
  | "request_research";

export type PostReviewResult =
  | { ok: true; body: Record<string, unknown> }
  | { ok: false; status: number; detail: string };

/** Shared version-bound partner review POST used by decisions queue + assessment ReviewPanel. */
export async function postReviewDecision(opts: {
  apiBase: string;
  assessmentId: string;
  revision: number;
  target: ReviewTarget;
  decision: ReviewDecision;
  comment: string;
  requestedItems?: string[];
  idempotencyPrefix?: string;
}): Promise<PostReviewResult> {
  const {
    apiBase,
    assessmentId,
    revision,
    target,
    decision,
    comment,
    requestedItems = [],
    idempotencyPrefix = "ui",
  } = opts;

  await ensureDemoSession(apiBase);
  const res = await fetch(`${apiBase}/api/v1/assessments/${assessmentId}/review`, {
    method: "POST",
    credentials: "include",
    headers: {
      "content-type": "application/json",
      "Idempotency-Key": crypto.randomUUID(),
    },
    body: JSON.stringify({
      target,
      decision,
      comment,
      requested_items: requestedItems,
      idempotency_key: `${idempotencyPrefix}-${assessmentId}-${revision}-${decision}-${Date.now()}`,
    }),
  });

  const raw = await res.text();
  let body: Record<string, unknown> = {};
  if (raw) {
    try {
      body = JSON.parse(raw) as Record<string, unknown>;
    } catch {
      body = { detail: raw };
    }
  }
  if (!res.ok) {
    return {
      ok: false,
      status: res.status,
      detail: String(body.detail || raw || res.status),
    };
  }
  return { ok: true, body };
}
