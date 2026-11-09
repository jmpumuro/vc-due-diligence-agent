"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icon, ThesisMark } from "./marks";
import ThemeToggle from "./ThemeToggle";

const ICONS = {
  runs: "M4 6h16M4 12h10M4 18h14",
  health: "M22 12h-4l-3 9L9 3l-3 9H2",
  recon: "M4 4v6h6M20 20v-6h-6M20 9A8 8 0 0 0 7.5 5.5M4 15a8 8 0 0 0 12.5 3.5",
  research: "M3 10.5L12 3l9 7.5V21a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1v-10.5z",
};

export default function ConsoleShell({
  children,
  title,
  crumbs,
  mode,
}: {
  children: React.ReactNode;
  title: string;
  crumbs?: string[];
  mode?: string | null;
}) {
  const pathname = usePathname();
  const crumbTrail = crumbs?.length ? crumbs : [title];
  const modeLabel = mode || "unknown";
  const modeOk = modeLabel === "live_ready" || modeLabel === "demo_ready";

  const operate = [
    { href: "/console", label: "Runs", icon: ICONS.runs, exact: true },
    { href: "/console/health", label: "Health", icon: ICONS.health },
    { href: "/console/reconciliation", label: "Outbox", icon: ICONS.recon },
  ];

  function isOn(href: string, exact?: boolean) {
    if (exact) return pathname === href;
    return pathname === href || pathname.startsWith(`${href}/`);
  }

  return (
    <div className="app">
      <div className="rail">
        <aside className="side">
          <div className="brandrow">
            <ThesisMark />
            <div className="nl nl-grow">
              <div className="brand-title">Default workspace</div>
              <div className="lbl">Thesis · local</div>
            </div>
          </div>

          <nav aria-label="Console" className="side-nav">
            <div className="sect">
              <span className="nl">Operate</span>
            </div>
            {operate.map((l) => (
              <Link
                key={l.href}
                href={l.href}
                className={`navi${isOn(l.href, l.exact) ? " on" : ""}`}
                title={l.label}
              >
                <span className="ic">
                  <Icon d={l.icon} />
                </span>
                <span className="nl nl-grow">{l.label}</span>
              </Link>
            ))}
            <div className="sect" style={{ marginTop: 10 }}>
              <span className="nl">Apps</span>
            </div>
            <Link href="/" className="navi" title="App">
              <span className="ic">
                <Icon d={ICONS.research} />
              </span>
              <span className="nl">App</span>
            </Link>
          </nav>

          <div className="sidefoot">
            <div className="navi" style={{ cursor: "default" }} title={modeLabel}>
              <span className="ic" style={{ width: 20, justifyContent: "center" }}>
                <span className="dot" style={{ background: modeOk ? "var(--green)" : "var(--amber)" }} />
              </span>
              <span className="nl nl-stack">
                <span className="side-meta">{modeLabel}</span>
                <span className="lbl">Ops console · Temporal + API</span>
              </span>
            </div>
          </div>
        </aside>
      </div>

      <main className="panel" style={{ flex: "1 1 0", minWidth: 0, display: "flex", flexDirection: "column" }}>
        <header className="top">
          <div className="crumbs">
            <span>Agent console</span>
            {crumbTrail.map((c, i) => (
              <span key={`${c}-${i}`} style={{ display: "inline-flex", gap: 8, alignItems: "center" }}>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                  <path d="M9 6l6 6-6 6" />
                </svg>
                <b>{c}</b>
              </span>
            ))}
          </div>
          <ThemeToggle />
        </header>
        <div className="page">{children}</div>
      </main>
    </div>
  );
}
