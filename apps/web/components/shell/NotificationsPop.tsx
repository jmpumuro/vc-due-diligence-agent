"use client";

import Link from "next/link";
import { useEffect } from "react";

export type NotificationItem = {
  id: string;
  title: string;
  detail?: string | null;
  when: string;
  href: string;
  dot?: string;
  unread?: boolean;
};

export default function NotificationsPop({
  open,
  onClose,
  items,
  onOpenItem,
  onMarkAllRead,
}: {
  open: boolean;
  onClose: () => void;
  items: NotificationItem[];
  onOpenItem?: (id: string) => void;
  onMarkAllRead?: () => void;
}) {
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const hasUnread = items.some((n) => n.unread && n.id !== "pending-decisions");

  return (
    <>
      <button
        type="button"
        className="scrim"
        aria-label="Dismiss notifications"
        onClick={onClose}
        style={{ background: "transparent", backdropFilter: "none", WebkitBackdropFilter: "none" }}
      />
      <div className="pop" role="dialog" aria-label="Notifications">
        <div className="ch">
          <h2>Notifications</h2>
          <div style={{ display: "flex", gap: 6 }}>
            {hasUnread && onMarkAllRead ? (
              <button type="button" className="btn btn-ghost btn-sm" onClick={onMarkAllRead}>
                Mark all read
              </button>
            ) : null}
            <button type="button" className="btn btn-ghost btn-sm" onClick={onClose}>
              Close
            </button>
          </div>
        </div>
        {!items.length ? (
          <div className="cb">
            <p className="mute flush">Nothing needs your attention right now.</p>
          </div>
        ) : (
          <div className="pop-list">
            {items.map((n) => (
              <Link
                key={n.id}
                className={`pitem${n.unread ? " unread" : ""}`}
                href={n.href}
                onClick={() => {
                  if (n.unread && n.id !== "pending-decisions") onOpenItem?.(n.id);
                  onClose();
                }}
              >
                <span
                  className="dot"
                  style={{ background: n.dot || "var(--blue)", marginTop: 6, flex: "none" }}
                />
                <span className="meta">
                  <strong>{n.title}</strong>
                  {n.detail ? <span className="mute mute-sm">{n.detail}</span> : null}
                  <span className="lbl">{n.when}</span>
                </span>
              </Link>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
