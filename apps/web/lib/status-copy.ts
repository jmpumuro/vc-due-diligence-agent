/** Partner-facing diligence copy — keep labels in sync with backend states/gates. */

export const assessmentStateCopy: Record<string, string> = {
  CREATED: "Queued",
  PLANNING: "Scoping workstreams",
  RESEARCHING: "Public research running",
  VALIDATING: "Checking sources",
  EVALUATING: "Weighing findings",
  CRITIQUING: "Stress-testing gaps",
  MEMO_READY: "Memo ready",
  AWAITING_REVIEW: "Ready for partner decision",
  INFORMATION_REQUESTED: "Waiting on company materials",
  DELIVERING: "Delivering",
  COMPLETED: "Decision recorded",
  REJECTED: "Passed",
  BLOCKED_CONFIGURATION: "Paused — setup needed",
  BUDGET_EXHAUSTED: "Budget exhausted",
  CANCELLED: "Cancelled",
  FAILED: "Research failed",
};

export const recommendationCopy: Record<string, string> = {
  advance: "Advance",
  hold: "Hold for more diligence",
  pass: "Pass",
  inconclusive: "Inconclusive — evidence thin",
};

/** Partner decision buttons — same glossary on decisions queue and assessment ReviewPanel. */
export const decisionActionCopy = {
  approve: "Advance",
  reject: "Pass",
  request_information: "Request information",
  request_research: "Ask for more research",
} as const;

export const recommendationBlurb: Record<string, string> = {
  advance: "Public evidence looks strong enough to take to the next diligence step.",
  hold: "Interesting, but open gaps should be closed before a commit.",
  pass: "Public evidence does not support moving forward at this time.",
  inconclusive: "Too little independent evidence to recommend a call either way.",
};

export const gateCopy: Record<string, string> = {
  sufficient: "Cleared",
  partial: "Needs more diligence",
  insufficient: "Open gap",
  not_applicable: "N/A",
  unavailable_at_level: "Not in this level",
};

export const trustCopy: Record<string, string> = {
  supported: "Source-backed",
  contested: "Contested",
  unsupported: "Unbacked",
  stale: "Stale",
  insufficient: "Not evidenced",
};

export const verificationCopy: Record<string, string> = {
  extracted: "Extracted",
  verified: "Partner-verified",
  contested: "Contested",
  rejected: "Rejected",
  insufficient: "Not evidenced",
};

export const domainCopy: Record<
  string,
  { name: string; scope: string; partnerAsk: string }
> = {
  company: {
    name: "Company",
    scope: "Identity, HQ, offering",
    partnerAsk: "Who is this company and what do they sell?",
  },
  team: {
    name: "Team",
    scope: "Founders and operators",
    partnerAsk: "Who are the named founders/execs, and is that public?",
  },
  market: {
    name: "Market",
    scope: "Segment and demand",
    partnerAsk: "What customer/segment do they serve?",
  },
  competition: {
    name: "Competition",
    scope: "Peers and substitutes",
    partnerAsk: "Who else competes, and how is differentiation framed?",
  },
  product: {
    name: "Product",
    scope: "Offering and packaging",
    partnerAsk: "What product capabilities are publicly evidenced?",
  },
  traction: {
    name: "Traction",
    scope: "Growth and logos",
    partnerAsk: "What customer or growth signals are public?",
  },
  financials: {
    name: "Financials",
    scope: "Revenue and funding",
    partnerAsk: "What funding/revenue figures are on the record?",
  },
  capitalization: {
    name: "Cap table / investors",
    scope: "Rounds and ownership signals",
    partnerAsk: "Which investors or ownership signals are public?",
  },
  legal: {
    name: "Legal",
    scope: "Entity, disputes, compliance",
    partnerAsk: "Any public legal or regulatory flags?",
  },
  security: {
    name: "Security",
    scope: "Controls and incidents",
    partnerAsk: "Any public security attestations or breaches?",
  },
  governance: {
    name: "Governance",
    scope: "Board and oversight",
    partnerAsk: "Is board/governance publicly described?",
  },
  thesis_fit: {
    name: "Thesis fit",
    scope: "Mandate alignment",
    partnerAsk: "Does the public mission align with the firm thesis?",
  },
};

export const tabCopy: Record<string, string> = {
  overview: "Overview",
  domains: "Workstreams",
  report: "Memo",
  contradictions: "Contested",
  risks: "Risks",
  requests: "Asks",
  dataroom: "Data room",
  financials: "Financials",
  sources: "Findings",
  history: "Activity",
};

export const levelCopy: Record<number, string> = {
  1: "Level 1 · Initial public screen",
  2: "Level 2 · Full public diligence",
  3: "Level 3 · Enhanced (data room)",
};

export function stateLabel(state: string): string {
  return assessmentStateCopy[state] || state;
}

export function recLabel(rec: string | null | undefined): string {
  if (!rec) return "—";
  return recommendationCopy[rec] || rec;
}

export function recBlurb(rec: string | null | undefined): string {
  if (!rec) return "No recommendation yet.";
  return recommendationBlurb[rec] || "";
}

export function gateLabel(gate: string | null | undefined): string {
  if (!gate) return "—";
  return gateCopy[gate] || gate;
}

export function trustLabel(trust: string | null | undefined): string {
  if (!trust) return "—";
  return trustCopy[trust] || trust;
}

export function verificationLabel(status: string | null | undefined): string {
  if (!status) return "—";
  return verificationCopy[status] || status;
}

export function domainMeta(domainId: string) {
  return (
    domainCopy[domainId] || {
      name: domainId.replace(/_/g, " "),
      scope: "",
      partnerAsk: "",
    }
  );
}

export function levelLabel(level: number): string {
  return levelCopy[level] || `Level ${level}`;
}

/**
 * Partner-facing research mode — speak about the agent, not a vendor or "model".
 * `agentUsed` maps from backend `llm_used` (implementation detail, not UI copy).
 */
export function agentModeLabel(agentUsed: boolean): string {
  return agentUsed ? "Agent research" : "Deterministic research";
}

export function agentModeDetail(agentUsed: boolean): string {
  return agentUsed
    ? "Agent public-web research"
    : "Deterministic public-web research";
}

export function agentAssistLabel(agentUsedAny: boolean): string {
  return agentUsedAny
    ? "Agent used on ≥1 workstream"
    : "Deterministic only so far";
}

export function agentSignalTag(agentUsed: boolean | null | undefined): string | null {
  if (agentUsed === true) return "agent";
  return null;
}

export function agentWorkstreamCell(agentUsed: boolean | null | undefined): string {
  if (agentUsed === true) return "agent";
  if (agentUsed === false) return "rules";
  return "—";
}

export const errorCopy: Record<string, string> = {
  STALE_REVIEW_TARGET: "This memo changed while you were reading it.",
  PROVIDER_NOT_CONFIGURED: "Live diligence needs setup first.",
  UNAUTHENTICATED: "Please sign in again.",
  FORBIDDEN: "Your role can't do that.",
  LEVEL_NOT_ALLOWED: "Your role can't start enhanced diligence.",
  LEVEL3_REQUIRES_DATA_ROOM: "Level 3 needs a deal team and data room.",
  LEVEL3_PRIVATE_PIPELINE_NOT_READY:
    "Level 3 screening needs OCR_PRODUCT_VERIFIED (D4 smoke green). You can still open the data-room shell.",
  ALREADY_AT_OR_ABOVE_LEVEL: "This assessment is already at that level.",
};
