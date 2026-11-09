"use client";

import { useEffect, useMemo, useState } from "react";
import { ensureDemoSession } from "@/lib/demo-session";
import {
  agentAssistLabel,
  agentSignalTag,
  agentWorkstreamCell,
} from "@/lib/status-copy";

type ProgressEvent = {
  event_id: number;
  event_type: string;
  domain_id: string | null;
  message: string;
  data: Record<string, unknown>;
  occurred_at: string | null;
};

type DomainMeta = {
  llm_used?: boolean;
  fetched?: boolean;
  independent_count?: number;
};

type Summary = {
  assessment_status: string;
  active_domains: string[];
  completed_domains: string[];
  claims_verified: number;
  claims_total: number | null;
  contradictions_detected: number;
  evidence_sufficiency: Record<string, string>;
  domain_meta: Record<string, DomainMeta>;
  llm_used_any: boolean;
  partial_results: boolean;
  provider_failures: number;
  human_review_status: string;
  last_event_id: number;
};

const DOMAIN_ORDER = [
  "company",
  "market",
  "product",
  "team",
  "thesis_fit",
  "traction",
  "financials",
  "competition",
  "legal",
  "security",
  "governance",
  "capitalization",
];

const emptySummary: Summary = {
  assessment_status: "unknown",
  active_domains: [],
  completed_domains: [],
  claims_verified: 0,
  claims_total: null,
  contradictions_detected: 0,
  evidence_sufficiency: {},
  domain_meta: {},
  llm_used_any: false,
  partial_results: false,
  provider_failures: 0,
  human_review_status: "none",
  last_event_id: 0,
};

function applyEvent(summary: Summary, ev: ProgressEvent): Summary {
  const data = ev.data || {};
  const next: Summary = {
    ...summary,
    evidence_sufficiency: { ...summary.evidence_sufficiency },
    domain_meta: { ...summary.domain_meta },
  };
  if (ev.event_type === "assessment.status" || ev.event_type === "stage") {
    next.assessment_status = String(data.status ?? ev.message);
  }
  if (ev.domain_id && ev.event_type === "domain.status") {
    const st = String(data.status || "");
    const active = new Set(next.active_domains);
    const completed = new Set(next.completed_domains);
    if (st === "completed") {
      completed.add(ev.domain_id);
      active.delete(ev.domain_id);
    } else if (st === "active" || st === "running" || st === "researching") {
      active.add(ev.domain_id);
      completed.delete(ev.domain_id);
    }
    next.active_domains = Array.from(active).sort();
    next.completed_domains = Array.from(completed).sort();
  }
  if (typeof data.claims_verified === "number") {
    next.claims_verified = Math.max(next.claims_verified, data.claims_verified);
  }
  if (typeof data.claims_total === "number") {
    next.claims_total = Math.max(next.claims_total ?? 0, data.claims_total);
  }
  if (typeof data.contradictions_detected === "number") {
    next.contradictions_detected = Math.max(
      next.contradictions_detected,
      data.contradictions_detected,
    );
  }
  if (typeof data.provider_failures === "number") {
    next.provider_failures = Math.max(next.provider_failures, data.provider_failures);
  }
  if (typeof data.human_review_status === "string") {
    next.human_review_status = data.human_review_status;
  }
  if (data.partial_results) next.partial_results = true;
  if (data.llm_used === true) next.llm_used_any = true;
  if (ev.domain_id && typeof data.evidence_sufficiency === "string") {
    next.evidence_sufficiency[ev.domain_id] = data.evidence_sufficiency;
  }
  if (ev.domain_id) {
    const meta = { ...(next.domain_meta[ev.domain_id] || {}) };
    if (typeof data.llm_used === "boolean") meta.llm_used = data.llm_used;
    if (typeof data.fetched === "boolean") meta.fetched = data.fetched;
    if (typeof data.independent_count === "number") {
      meta.independent_count = data.independent_count;
    }
    next.domain_meta[ev.domain_id] = meta;
  }
  next.last_event_id = Math.max(next.last_event_id, ev.event_id);
  return next;
}

function enrichFromEvents(base: Partial<Summary> | undefined, events: ProgressEvent[]): Summary {
  const start: Summary = {
    ...emptySummary,
    ...(base || {}),
    evidence_sufficiency: { ...(base?.evidence_sufficiency || {}) },
    domain_meta: { ...(base?.domain_meta || {}) },
    active_domains: [...(base?.active_domains || [])],
    completed_domains: [...(base?.completed_domains || [])],
  };
  return events.reduce((s, ev) => applyEvent(s, ev), start);
}

function domainRows(summary: Summary) {
  const seen = new Set([
    ...summary.active_domains,
    ...summary.completed_domains,
    ...Object.keys(summary.evidence_sufficiency),
    ...Object.keys(summary.domain_meta),
  ]);
  const ordered = [
    ...DOMAIN_ORDER.filter((d) => seen.has(d)),
    ...Array.from(seen).filter((d) => !DOMAIN_ORDER.includes(d)).sort(),
  ];
  return ordered.map((id) => {
    let status = "pending";
    if (summary.completed_domains.includes(id)) status = "completed";
    else if (summary.active_domains.includes(id)) status = "active";
    const meta = summary.domain_meta[id] || {};
    return {
      id,
      status,
      sufficiency: summary.evidence_sufficiency[id],
      llm: meta.llm_used,
      fetched: meta.fetched,
      independent: meta.independent_count,
    };
  });
}

export default function ProgressPanel({
  assessmentId,
  apiBase = "",
}: {
  assessmentId: string;
  apiBase?: string;
}) {
  // Prefer same-origin BFF (empty apiBase). Ignore absolute cross-origin hosts.
  const base = !apiBase || /localhost:8001|127\.0\.0\.1:8001|:8000\b/.test(apiBase) ? "" : apiBase;
  const [summary, setSummary] = useState<Summary>(emptySummary);
  const [events, setEvents] = useState<ProgressEvent[]>([]);
  const [conn, setConn] = useState<"connecting" | "live" | "polling" | "error">("connecting");

  const streamUrl = useMemo(
    () => `${base}/api/v1/assessments/${assessmentId}/progress/stream`,
    [base, assessmentId],
  );
  const snapshotUrl = useMemo(
    () => `${base}/api/v1/assessments/${assessmentId}/progress`,
    [base, assessmentId],
  );

  useEffect(() => {
    let es: EventSource | null = null;
    let cancelled = false;
    let pollTimer: ReturnType<typeof setInterval> | null = null;
    let errorStreak = 0;

    async function ensureBrowserSession() {
      const probe = await fetch(snapshotUrl, { credentials: "include", cache: "no-store" });
      if (probe.status !== 401) return probe;
      await ensureDemoSession(base);
      return fetch(snapshotUrl, { credentials: "include", cache: "no-store" });
    }

    function ingestSnapshot(body: {
      summary?: Partial<Summary>;
      events?: ProgressEvent[];
    }) {
      const evs = Array.isArray(body.events) ? body.events.slice(-40) : [];
      setEvents(evs);
      setSummary(enrichFromEvents(body.summary, evs));
      const last = evs[evs.length - 1];
      if (last) {
        sessionStorage.setItem(`thesis-progress-${assessmentId}`, String(last.event_id));
      }
    }

    async function pullSnapshot() {
      try {
        const snap = await ensureBrowserSession();
        if (!snap.ok) return false;
        ingestSnapshot(await snap.json());
        return true;
      } catch {
        return false;
      }
    }

    function startPolling() {
      if (pollTimer || cancelled) return;
      setConn((c) => (c === "live" ? c : "polling"));
      pollTimer = setInterval(() => {
        void pullSnapshot();
      }, 4000);
    }

    async function bootstrap() {
      const ok = await pullSnapshot();
      if (cancelled) return;
      if (!ok) {
        setConn("error");
        startPolling();
      }

      const lastId =
        typeof window !== "undefined"
          ? sessionStorage.getItem(`thesis-progress-${assessmentId}`) || ""
          : "";
      const url = lastId ? `${streamUrl}?last_event_id=${lastId}` : streamUrl;
      try {
        es = new EventSource(url, { withCredentials: true });
      } catch {
        setConn("error");
        startPolling();
        return;
      }

      es.addEventListener("progress", (msg) => {
        errorStreak = 0;
        const ev = JSON.parse((msg as MessageEvent).data) as ProgressEvent;
        sessionStorage.setItem(`thesis-progress-${assessmentId}`, String(ev.event_id));
        setEvents((prev) => {
          if (prev.some((p) => p.event_id === ev.event_id)) return prev;
          return [...prev, ev].slice(-40);
        });
        setSummary((s) => applyEvent(s, ev));
        setConn("live");
        if (pollTimer) {
          clearInterval(pollTimer);
          pollTimer = null;
        }
      });
      es.onopen = () => {
        errorStreak = 0;
        setConn("live");
      };
      es.onerror = () => {
        errorStreak += 1;
        if (errorStreak >= 2) {
          setConn((c) => (c === "live" ? "polling" : "error"));
          startPolling();
        }
      };
    }

    bootstrap();
    return () => {
      cancelled = true;
      es?.close();
      if (pollTimer) clearInterval(pollTimer);
    };
  }, [assessmentId, base, snapshotUrl, streamUrl]);

  const claimProgress =
    summary.claims_total != null
      ? `${summary.claims_verified} / ${summary.claims_total} claims verified`
      : `${summary.claims_verified} claims verified`;

  const rows = domainRows(summary);
  const streamLabel =
    conn === "live"
      ? "live"
      : conn === "polling"
        ? "polling"
        : conn === "connecting"
          ? "connecting"
          : "offline — retrying";

  return (
    <section className="card progress-panel">
      <div className="ch">
        <h2>Research progress</h2>
        <span className="pill">
          <span
            className="dot"
            style={{
              background:
                conn === "live"
                  ? "var(--green)"
                  : conn === "polling" || conn === "connecting"
                    ? "var(--amber)"
                    : "var(--red)",
            }}
          />
          {streamLabel}
        </span>
      </div>
      <div className="row">
        <span>Screen status</span>
        <span className="mono">{summary.assessment_status}</span>
      </div>
      <div className="row">
        <span>Findings checked</span>
        <span>{claimProgress}</span>
      </div>
      <div className="row">
        <span>Contested items</span>
        <span>{summary.contradictions_detected}</span>
      </div>
      <div className="row">
        <span>Agent assist</span>
        <span>{agentAssistLabel(summary.llm_used_any)}</span>
      </div>
      <div className="row">
        <span>Partner review</span>
        <span>{summary.human_review_status}</span>
      </div>
      {summary.partial_results && (
        <div className="row">
          <span>Partial results</span>
          <span>yes — some sources still thin</span>
        </div>
      )}

      <div className="ch" style={{ borderTop: "1px solid var(--border)" }}>
        <h2>Workstreams</h2>
        <span className="lbl">
          {summary.completed_domains.length} done
          {summary.active_domains.length
            ? ` · ${summary.active_domains.length} active`
            : ""}
        </span>
      </div>
      {!rows.length ? (
        <div className="cb">
          <p className="mute" style={{ margin: 0 }}>
            Waiting for domain progress events…
          </p>
        </div>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Workstream</th>
              <th>Status</th>
              <th>Diligence bar</th>
              <th>Page fetch</th>
              <th>Agent</th>
              <th>Indep. sources</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td style={{ textTransform: "capitalize" }}>{r.id.replace(/_/g, " ")}</td>
                <td>
                  <span className="pill">
                    <span
                      className="dot"
                      style={{
                        background:
                          r.status === "completed"
                            ? "var(--green)"
                            : r.status === "active"
                              ? "var(--amber)"
                              : "var(--border-strong)",
                      }}
                    />
                    {r.status}
                  </span>
                </td>
                <td className="mute">
                  {r.sufficiency === "sufficient"
                    ? "Cleared"
                    : r.sufficiency === "partial"
                      ? "Needs more"
                      : r.sufficiency === "insufficient"
                        ? "Open gap"
                        : r.sufficiency || "—"}
                </td>
                <td className="mute">
                  {r.fetched === true ? "live page" : r.fetched === false ? "unavailable" : "—"}
                </td>
                <td className="mute">
                  {agentWorkstreamCell(r.llm)}
                </td>
                <td className="mute">
                  {typeof r.independent === "number" ? r.independent : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <div className="ch" style={{ borderTop: "1px solid var(--border)" }}>
        <h2>Live events</h2>
        <span className="lbl">{events.length} recent</span>
      </div>
      <ul className="event-log">
        {events
          .slice()
          .reverse()
          .slice(0, 12)
          .map((ev) => {
            const d = ev.data || {};
            const bits = [
              typeof d.evidence_sufficiency === "string" ? `gate=${d.evidence_sufficiency}` : null,
              agentSignalTag(d.llm_used === true),
              d.fetched === true ? "fetched" : d.fetched === false ? "stub" : null,
              typeof d.independent_count === "number" ? `indep=${d.independent_count}` : null,
            ].filter(Boolean);
            return (
              <li key={ev.event_id}>
                <code>{ev.event_id}</code> {ev.event_type}
                {ev.domain_id ? ` · ${ev.domain_id}` : ""} — {ev.message}
                {bits.length ? ` (${bits.join(", ")})` : ""}
              </li>
            );
          })}
        {!events.length && (
          <li className="mute">No events yet — stream will fill as the worker runs.</li>
        )}
      </ul>
    </section>
  );
}
