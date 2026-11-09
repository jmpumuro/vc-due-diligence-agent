"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import {
  formatNotificationWhen,
  notificationTone,
  partnerNotifications,
  type ApiNotification,
} from "@/lib/notifications";
import CommandPalette from "./CommandPalette";
import { Icon, ThesisMark } from "./marks";
import NotificationsPop, { type NotificationItem } from "./NotificationsPop";
import ThemeToggle from "./ThemeToggle";

const ICONS = {
  home: "M3 10.5L12 3l9 7.5V21a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1v-10.5z",
  companies: "M4 21V5a2 2 0 0 1 2-2h6v18H4zm10 0V10h6a2 2 0 0 1 2 2v9h-8z",
  decisions: "M9 11l3 3L22 4M4 20h16",
  watchlist: "M12 3l2.4 7.2H22l-6 4.4 2.3 7.1L12 17.6 5.7 21.7 8 14.6 2 10.2h7.6L12 3z",
  thesis: "M4 5h16v14H4zM8 9h8M8 13h5",
  settings:
    "M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7zM19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9c.1.7.7 1.2 1.5 1.2H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z",
  console: "M4 5h16v11H4zM8 20h8M12 16v4M8 9l2 2-2 2M12 13h4",
};

export default function ResearchShell({
  children,
  title,
  crumbs,
  pendingDecisions = 0,
  demo = false,
  mode,
  statusLine,
}: {
  children: React.ReactNode;
  title: string;
  crumbs?: string[];
  pendingDecisions?: number;
  demo?: boolean;
  mode?: string;
  statusLine?: string;
}) {
  const pathname = usePathname();
  const [pinned, setPinned] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [bellOpen, setBellOpen] = useState(false);
  const [notes, setNotes] = useState<NotificationItem[]>([]);
  const crumbTrail = crumbs?.length ? crumbs : [title];

  async function markNotificationsRead(ids?: string[]) {
    const payload =
      ids && ids.length
        ? { ids: ids.filter((id) => id !== "pending-decisions") }
        : {};
    if (ids && !(payload as { ids?: string[] }).ids?.length) return;
    try {
      await fetch("/api/v1/notifications/mark-read", {
        method: "POST",
        credentials: "include",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      });
      setNotes((prev) =>
        prev.map((n) => {
          if (n.id === "pending-decisions") return n;
          if (!ids) return { ...n, unread: false };
          return ids.includes(n.id) ? { ...n, unread: false } : n;
        }),
      );
    } catch {
      /* best-effort */
    }
  }

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setBellOpen(false);
        setPaletteOpen((v) => !v);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const fallback: NotificationItem[] =
        pendingDecisions > 0
          ? [
              {
                id: "pending-decisions",
                title: `${pendingDecisions} compan${pendingDecisions === 1 ? "y" : "ies"} ready for decision`,
                detail: "Open the decisions queue to advance or pass.",
                when: "Needs you",
                href: "/decisions",
                dot: "var(--brand)",
                unread: true,
              },
            ]
          : [];
      try {
        const res = await fetch("/api/v1/notifications?limit=40", {
          credentials: "include",
          cache: "no-store",
        });
        if (!res.ok) {
          if (!cancelled) setNotes(fallback);
          return;
        }
        const body = (await res.json()) as { items?: ApiNotification[] };
        const shaped = partnerNotifications(body.items || []).map((n) => ({
          id: n.id,
          title: n.title || "Notification",
          detail: n.body,
          when: formatNotificationWhen(n.created_at),
          href: n.subject_id ? `/companies/a/${n.subject_id}` : "/decisions",
          dot: notificationTone(n.event_type, n.body),
          unread: !n.read_at,
        }));
        if (!cancelled) setNotes(shaped.length ? shaped : fallback);
      } catch {
        if (!cancelled) setNotes(fallback);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [pendingDecisions]);

  const mainLinks = [
    { href: "/", label: "Home", icon: ICONS.home, exact: true },
    { href: "/companies", label: "Companies", icon: ICONS.companies },
    {
      href: "/decisions",
      label: "Decisions",
      icon: ICONS.decisions,
      badge: pendingDecisions || undefined,
    },
    { href: "/watchlist", label: "Watchlist", icon: ICONS.watchlist },
  ];
  const firmLinks = [
    { href: "/thesis", label: "Investment thesis", icon: ICONS.thesis },
    { href: "/settings", label: "Settings", icon: ICONS.settings },
  ];

  function isOn(href: string, exact?: boolean) {
    if (exact) return pathname === href;
    return pathname === href || pathname.startsWith(`${href}/`);
  }

  const statusDot =
    mode === "setup_required" ? "var(--amber)" : demo ? "var(--blue)" : "var(--green)";
  const statusLabel =
    mode === "setup_required" ? "Setup required" : demo ? "Demo workspace" : "Live ready";

  return (
    <div className={`app${pinned ? " pinned" : ""}`}>
      <div className="rail">
        <aside className="side">
          <div className="brandrow">
            <ThesisMark />
            <div className="nl nl-grow">
              <div className="brand-title">Default workspace</div>
              <div className="lbl">Free · self-hosted</div>
            </div>
          </div>

          <nav aria-label="Main" className="side-nav">
            <div className="sect">
              <span className="nl">Workspace</span>
            </div>
            {mainLinks.map((l) => (
              <Link
                key={l.href}
                href={l.href}
                className={`navi${isOn(l.href, l.exact) ? " on" : ""}`}
                title={l.label}
              >
                <span className="ic">
                  <Icon d={l.icon} />
                  {l.badge ? <span className="bdot" /> : null}
                </span>
                <span className="nl nl-grow">{l.label}</span>
                {l.badge ? <span className="badge nl">{l.badge}</span> : null}
              </Link>
            ))}
            <div className="sect" style={{ marginTop: 10 }}>
              <span className="nl">Firm</span>
            </div>
            {firmLinks.map((l) => (
              <Link
                key={l.href}
                href={l.href}
                className={`navi${isOn(l.href) ? " on" : ""}`}
                title={l.label}
              >
                <span className="ic">
                  <Icon d={l.icon} />
                </span>
                <span className="nl nl-grow">{l.label}</span>
              </Link>
            ))}
            <div className="sect">
              <span className="nl">Admin</span>
            </div>
            <Link href="/console" className="navi" title="Agent console">
              <span className="ic">
                <Icon d={ICONS.console} />
              </span>
              <span className="nl">Agent console</span>
            </Link>
          </nav>

          <div className="sidefoot">
            <div className="navi" style={{ cursor: "default" }} title={statusLabel}>
              <span className="ic" style={{ width: 20, justifyContent: "center" }}>
                <span className="dot" style={{ background: statusDot }} />
              </span>
              <span className="nl nl-stack">
                <span className="side-meta">{statusLabel}</span>
                <span className="lbl">{statusLine || "Local stack"}</span>
              </span>
            </div>
            <div className="side-user">
              <span className="avatar">P</span>
              <span className="nl nl-grow nl-stack">
                <span className="name">Partner</span>
                <span className="lbl">Partner · Admin</span>
              </span>
              <button
                type="button"
                className="iconbtn nl"
                style={{ width: 32, height: 32 }}
                aria-pressed={pinned}
                aria-label={pinned ? "Unpin sidebar" : "Pin sidebar"}
                onClick={() => setPinned((p) => !p)}
                title="Pin sidebar"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9">
                  <path d={pinned ? "M6 6l12 12M6 18L18 6" : "M12 17v5M9 10V4h6v6l2 3H7l2-3z"} />
                </svg>
              </button>
            </div>
          </div>
        </aside>
      </div>

      <main className="panel" style={{ flex: "1 1 0", minWidth: 0, display: "flex", flexDirection: "column" }}>
        <header className="top">
          <div className="crumbs">
            <span>App</span>
            {crumbTrail.map((c, i) => (
              <span key={`${c}-${i}`} style={{ display: "inline-flex", gap: 8, alignItems: "center" }}>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                  <path d="M9 6l6 6-6 6" />
                </svg>
                <b>{c}</b>
              </span>
            ))}
          </div>
          <button
            type="button"
            className="search"
            aria-label="Search and commands"
            onClick={() => {
              setBellOpen(false);
              setPaletteOpen(true);
            }}
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="11" cy="11" r="7" />
              <path d="M20 20l-3.5-3.5" />
            </svg>
            <span style={{ flex: 1, textAlign: "left", fontSize: 13 }}>Search companies or jump to…</span>
            <span className="kbd">⌘K</span>
          </button>
          <div className="bell-wrap">
            <button
              type="button"
              className="iconbtn"
              aria-label="Notifications"
              title="Notifications"
              aria-pressed={bellOpen}
              onClick={() => {
                setPaletteOpen(false);
                setBellOpen((v) => !v);
              }}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                <path d="M6 8a6 6 0 1 1 12 0c0 7 3 8 3 8H3s3-1 3-8M10.3 21a1.9 1.9 0 0 0 3.4 0" />
              </svg>
              {notes.some((n) => n.unread) || pendingDecisions > 0 ? (
                <span className="notif-badge" aria-hidden="true" />
              ) : null}
            </button>
            <NotificationsPop
              open={bellOpen}
              onClose={() => setBellOpen(false)}
              items={notes}
              onOpenItem={(id) => void markNotificationsRead([id])}
              onMarkAllRead={() => void markNotificationsRead()}
            />
          </div>
          <ThemeToggle />
          <Link className="btn btn-primary" href="/companies/new">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
              <path d="M12 5v14M5 12h14" />
            </svg>
            New diligence
          </Link>
        </header>

        <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />

        {(demo || mode === "setup_required") && (
          <div className="notice">
            <span
              className="dot"
              style={{ background: mode === "setup_required" ? "var(--amber)" : "var(--blue)" }}
            />
            <span style={{ flex: "1 1 320px" }}>
              {mode === "setup_required"
                ? "Live diligence is paused until setup is complete."
                : "Demo workspace seed is loaded on this stack. New Level 1/2 runs use the configured provider when a key is present."}
            </span>
            {mode === "setup_required" ? (
              <Link className="btn btn-sm" href="/setup">
                Complete setup
              </Link>
            ) : null}
            <Link href="/console" className="lbl">
              View in agent console
            </Link>
          </div>
        )}

        <div className="page">{children}</div>
      </main>
    </div>
  );
}
