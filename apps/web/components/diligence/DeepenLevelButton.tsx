"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { ensureDemoSession } from "@/lib/demo-session";
import { errorCopy } from "@/lib/status-copy";

const BLOCKED = new Set([
  "RESEARCHING",
  "PLANNING",
  "VALIDATING",
  "EVALUATING",
  "CRITIQUING",
]);

export default function DeepenLevelButton({
  apiBase,
  assessmentId,
  level,
  state,
}: {
  apiBase: string;
  assessmentId: string;
  level: number;
  state: string;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (level >= 3 || BLOCKED.has(state)) return null;

  const target = level + 1;
  const label =
    target === 2 ? "Deepen to Level 2" : "Deepen to Level 3";

  async function deepen() {
    setBusy(true);
    setError(null);
    try {
      await ensureDemoSession(apiBase);
      const res = await fetch(`${apiBase}/api/v1/assessments/${assessmentId}/deepen`, {
        method: "POST",
        credentials: "include",
        headers: {
          "content-type": "application/json",
          "Idempotency-Key": crypto.randomUUID(),
        },
        body: JSON.stringify({ target_level: target, start_screening: true }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        const detail = String(body.detail || res.status);
        setError(errorCopy[detail] || detail);
        return;
      }
      router.refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
      <button type="button" className="btn btn-primary" disabled={busy} onClick={deepen}>
        {busy ? "Starting…" : label}
      </button>
      {error ? <span className="err">{error}</span> : null}
    </span>
  );
}
