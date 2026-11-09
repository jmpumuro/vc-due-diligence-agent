/** Shared display helpers for diligence UI. */

export function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase() || "")
    .join("");
}

/** Single-letter avatar for compact rows (decisions list). */
export function avatarLetter(name: string): string {
  const ch = (name.trim()[0] || "?").toLowerCase();
  return /[a-z0-9]/.test(ch) ? ch : "?";
}

export function normalizeLikelihood(raw?: string | null): "high" | "medium" | "low" {
  const v = (raw || "medium").toLowerCase();
  if (v === "high" || v === "likely" || v === "probable") return "high";
  if (v === "low" || v === "possible" || v === "unlikely" || v === "remote") return "low";
  return "medium";
}

export function recTone(rec?: string | null): string {
  switch ((rec || "").toLowerCase()) {
    case "advance":
      return "var(--green)";
    case "pass":
      return "var(--red)";
    case "inconclusive":
      return "var(--gray)";
    case "hold":
    default:
      return "var(--amber)";
  }
}

export function assessmentStateColor(state: string): string {
  if (state === "AWAITING_REVIEW" || state === "MEMO_READY") return "var(--amber)";
  if (state === "COMPLETED") return "var(--green)";
  if (state.includes("FAIL") || state.includes("ERROR")) return "var(--red)";
  return "var(--blue)";
}

/** Gate / workstream tone — keep ResearchBrief, DomainTable, pills in sync. */
export function gateColor(gate?: string | null): string {
  switch (gate) {
    case "sufficient":
      return "var(--green)";
    case "partial":
      return "var(--amber)";
    case "insufficient":
      return "var(--red)";
    default:
      return "var(--gray)";
  }
}

export function workstreamDotColor(status: string, gate: string): string {
  if (status === "running" || status === "active") return "var(--blue)";
  return gateColor(gate);
}

/** Color for agent vs deterministic research mode pills. */
export function researchModeColor(agentUsed: boolean): string {
  return agentUsed ? "var(--blue)" : "var(--gray)";
}
