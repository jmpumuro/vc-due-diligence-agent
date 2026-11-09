"use client";

import { useState } from "react";
import DecideDrawer from "@/components/diligence/DecideDrawer";
import type { ReviewTarget } from "@/lib/review-api";

export default function DecideChrome({
  companyName,
  level,
  revision,
  apiBase,
  assessmentId,
  target,
  state,
  canDecide,
  draftRequests = [],
}: {
  companyName: string;
  level: number;
  revision: number;
  apiBase: string;
  assessmentId: string;
  target: ReviewTarget | null;
  state: string;
  canDecide: boolean;
  draftRequests?: string[];
}) {
  const [open, setOpen] = useState(false);
  if (!canDecide) return null;

  return (
    <>
      <button type="button" className="btn btn-primary" onClick={() => setOpen(true)}>
        Decide
      </button>
      <DecideDrawer
        open={open}
        onClose={() => setOpen(false)}
        companyName={companyName}
        level={level}
        revision={revision}
        apiBase={apiBase}
        assessmentId={assessmentId}
        target={target}
        state={state}
        draftRequests={draftRequests}
      />
    </>
  );
}
