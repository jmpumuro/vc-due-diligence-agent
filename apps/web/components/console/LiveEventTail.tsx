"use client";

import { useEffect, useState } from "react";
import { publicApiBase } from "@/lib/api";
import { ensureDemoSession } from "@/lib/demo-session";

type Ev = {
  event_id: number;
  assessment_id: string;
  event_type: string;
  domain_id: string | null;
  message: string;
  occurred_at: string | null;
};

export default function LiveEventTail() {
  const [items, setItems] = useState<Ev[]>([]);
  const [state, setState] = useState<"loading" | "live" | "error">("loading");
  const api = publicApiBase();

  useEffect(() => {
    let cancelled = false;

    async function tick() {
      try {
        await ensureDemoSession(api);
        const res = await fetch(`${api}/api/v1/ops/events?limit=25`, {
          credentials: "include",
          cache: "no-store",
        });
        if (!res.ok) throw new Error(String(res.status));
        const body = await res.json();
        if (!cancelled) {
          setItems(Array.isArray(body.items) ? body.items : []);
          setState("live");
        }
      } catch {
        if (!cancelled) setState("error");
      }
    }

    tick();
    const id = setInterval(tick, 5000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [api]);

  return (
    <section className="card">
      <div className="ch">
        <h2>Live events</h2>
        <span className="pill">
          <span
            className="dot"
            style={{
              background:
                state === "live"
                  ? "var(--green)"
                  : state === "loading"
                    ? "var(--amber)"
                    : "var(--red)",
            }}
          />
          {state}
        </span>
      </div>
      {!items.length ? (
        <div className="cb">
          <p className="mute" style={{ margin: 0 }}>
            {state === "error"
              ? "Could not load ops events."
              : "No progress events yet."}
          </p>
        </div>
      ) : (
        <ul className="event-log" style={{ marginTop: 0 }}>
          {items.map((ev) => (
            <li key={ev.event_id}>
              <code>{ev.event_id}</code> {ev.event_type}
              {ev.domain_id ? ` · ${ev.domain_id}` : ""} — {ev.message}
              <span className="mute"> · {ev.assessment_id.slice(0, 8)}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
