"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

const COMMANDS = [
  { label: "Home", hint: "Workspace overview", href: "/" },
  { label: "Companies", hint: "Portfolio list", href: "/companies" },
  { label: "New diligence", hint: "Start a screening", href: "/companies/new" },
  { label: "Decisions", hint: "Partner review queue", href: "/decisions" },
  { label: "Watchlist", hint: "Change monitoring", href: "/watchlist" },
  { label: "Investment thesis", hint: "Mandate and rubric", href: "/thesis" },
  { label: "Settings", hint: "Private AI and retention", href: "/settings" },
  { label: "Agent console", hint: "Runs and health", href: "/console" },
];

export default function CommandPalette({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const router = useRouter();
  const [q, setQ] = useState("");

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return COMMANDS;
    return COMMANDS.filter(
      (c) => c.label.toLowerCase().includes(needle) || c.hint.toLowerCase().includes(needle),
    );
  }, [q]);

  useEffect(() => {
    if (!open) setQ("");
  }, [open]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape" && open) {
        e.preventDefault();
        onClose();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="overlay" role="presentation" onClick={onClose}>
      <div
        className="palette"
        role="dialog"
        aria-label="Command palette"
        onClick={(e) => e.stopPropagation()}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            padding: "14px 16px",
            borderBottom: "1px solid var(--border)",
          }}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--muted)" strokeWidth="2">
            <circle cx="11" cy="11" r="7" />
            <path d="M20 20l-3.5-3.5" />
          </svg>
          <input
            autoFocus
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Type a company or command"
            style={{
              flex: 1,
              width: "100%",
              border: 0,
              outline: 0,
              background: "transparent",
              fontSize: 15,
              color: "var(--text)",
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter" && filtered[0]) {
                router.push(filtered[0].href);
                onClose();
              }
            }}
          />
          <button type="button" className="kbd" style={{ cursor: "pointer" }} onClick={onClose}>
            Esc
          </button>
        </div>
        <div className="sect" style={{ padding: "12px 16px 4px", height: "auto" }}>
          Jump to
        </div>
        {filtered.map((c) => (
          <button
            key={c.href}
            type="button"
            className="pitem"
            onClick={() => {
              router.push(c.href);
              onClose();
            }}
          >
            <span style={{ flex: 1, textAlign: "left" }}>
              <span style={{ fontWeight: 500 }}>{c.label}</span>
              <span className="lbl" style={{ display: "block" }}>
                {c.hint}
              </span>
            </span>
          </button>
        ))}
        {!filtered.length ? (
          <div className="cb">
            <p className="mute" style={{ margin: 0 }}>
              No matches.
            </p>
          </div>
        ) : null}
      </div>
    </div>
  );
}
