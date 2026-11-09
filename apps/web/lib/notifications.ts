/** Partner-facing notification shaping — hide noisy agent internals. */

const PARTNER_EVENTS = new Set([
  "review.requested",
  "review.decided",
  "assessment.memo_ready",
  "watchlist.reassess",
]);

const PARTNER_STATES = new Set([
  "AWAITING_REVIEW",
  "COMPLETED",
  "REJECTED",
  "FAILED",
  "INFORMATION_REQUESTED",
  "BLOCKED_CONFIGURATION",
]);

export type ApiNotification = {
  id: string;
  title: string;
  body?: string | null;
  company_name?: string | null;
  subject_id?: string | null;
  created_at?: string | null;
  event_type?: string;
  read_at?: string | null;
};

export function notificationTone(eventType?: string, body?: string | null): string {
  const t = eventType || "";
  if (t.includes("review") || t.includes("memo")) return "var(--brand)";
  if (t.includes("fail") || (body || "").toUpperCase().includes("FAILED")) return "var(--red)";
  if ((body || "").toUpperCase().includes("AWAITING")) return "var(--amber)";
  return "var(--blue)";
}

/** Drop intermediate screening ticks; keep one meaningful item per assessment+event. */
export function partnerNotifications(items: ApiNotification[]): ApiNotification[] {
  const filtered = items.filter((n) => {
    const t = n.event_type || "";
    if (PARTNER_EVENTS.has(t)) return true;
    if (t === "assessment.state_changed") {
      const state = (n.body || "").replace(/^State:\s*/i, "").trim().toUpperCase();
      // New copy may put state alone in body, or title already partnerized.
      if (PARTNER_STATES.has(state)) return true;
      if (/ready for partner|completed|failed|paused|waiting on company|passed/i.test(n.title)) {
        return true;
      }
      return false;
    }
    return false;
  });

  const seen = new Set<string>();
  const out: ApiNotification[] = [];
  for (const n of filtered) {
    const key = `${n.event_type || ""}:${n.subject_id || n.id}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(n);
  }
  return out;
}

export function formatNotificationWhen(iso?: string | null): string {
  if (!iso) return "Recently";
  try {
    return new Date(iso).toLocaleString("en-GB", {
      day: "numeric",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "Recently";
  }
}
