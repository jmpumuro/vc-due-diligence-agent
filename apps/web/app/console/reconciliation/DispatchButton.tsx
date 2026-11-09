"use client";

import { useState } from "react";
import { publicApiBase } from "@/lib/api";
import { ensureDemoSession } from "@/lib/demo-session";

export default function DispatchButton() {
  const [msg, setMsg] = useState<string | null>(null);
  async function run() {
    const api = publicApiBase();
    await ensureDemoSession(api);
    const res = await fetch(`${api}/api/v1/ops/outbox/dispatch`, {
      method: "POST",
      credentials: "include",
    });
    const body = await res.json().catch(() => ({}));
    setMsg(res.ok ? `Delivered ${body.delivered}` : `Failed ${res.status}`);
  }
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <button className="btn" type="button" onClick={run}>
        Dispatch pending
      </button>
      {msg && <span className="mute">{msg}</span>}
    </div>
  );
}
