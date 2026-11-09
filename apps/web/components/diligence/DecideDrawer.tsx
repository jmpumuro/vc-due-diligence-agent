"use client";

import ReviewPanel from "@/app/(diligence)/companies/a/[assessmentId]/ReviewPanel";
import { initials } from "@/lib/format";
import type { ReviewTarget } from "@/lib/review-api";

export default function DecideDrawer({
  open,
  onClose,
  companyName,
  level,
  revision,
  apiBase,
  assessmentId,
  target,
  state,
  draftRequests = [],
}: {
  open: boolean;
  onClose: () => void;
  companyName: string;
  level: number;
  revision: number;
  apiBase: string;
  assessmentId: string;
  target: ReviewTarget | null;
  state: string;
  draftRequests?: string[];
}) {
  if (!open) return null;

  return (
    <>
      <button type="button" className="scrim" aria-label="Close decision panel" onClick={onClose} />
      <aside className="drawer" role="dialog" aria-label={`Decide on ${companyName}`}>
        <div className="drawer-head">
          <span
            className="logo"
            style={{
              background: "var(--brand-soft)",
              color: "var(--brand-text)",
              borderColor: "transparent",
            }}
          >
            {initials(companyName)}
          </span>
          <span className="vstack" style={{ flex: 1 }}>
            <span className="disp">Decide on {companyName}</span>
            <span className="lbl">
              Level {level} · revision {revision} · applies to this version only
            </span>
          </span>
          <button type="button" className="iconbtn" aria-label="Close" onClick={onClose}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M6 6l12 12M18 6L6 18" />
            </svg>
          </button>
        </div>
        <div className="drawer-body">
          <ReviewPanel
            apiBase={apiBase}
            assessmentId={assessmentId}
            revision={revision}
            target={target}
            state={state}
            draftRequests={draftRequests}
          />
        </div>
      </aside>
    </>
  );
}
