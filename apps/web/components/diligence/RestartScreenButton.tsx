"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { ensureDemoSession } from "@/lib/demo-session";

const RESTARTABLE = new Set(["CREATED", "FAILED", "INFORMATION_REQUESTED"]);

export default function RestartScreenButton({
  apiBase,
  assessmentId,
  state,
  level,
}: {
  apiBase: string;
  assessmentId: string;
  state: string;
  level: number;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // L1–L3 public re-run; API enforces OCR gate for Level 3.
  if (level > 3 || !RESTARTABLE.has(state)) return null;

  async function restart() {
    setBusy(true);
    setError(null);
    try {
      await ensureDemoSession(apiBase);
      const res = await fetch(`${apiBase}/api/v1/assessments/${assessmentId}/screen`, {
        method: "POST",
        credentials: "include",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ level }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(String(body.detail || res.status));
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
    <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
      <button type="button" className="btn" disabled={busy} onClick={restart}>
        {busy ? "Starting…" : "Re-run public screen"}
      </button>
      {error ? <span className="err">{error}</span> : null}
    </span>
  );
}
