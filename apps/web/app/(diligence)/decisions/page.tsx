import Link from "next/link";
import ResearchShell from "@/components/shell/ResearchShell";
import StatusPill from "@/components/ui/StatusPill";
import { apiJson, publicApiBase } from "@/lib/api";
import { avatarLetter, recTone } from "@/lib/format";
import { sessionCookie } from "@/lib/session";
import { recBlurb, recLabel } from "@/lib/status-copy";
import DecisionActions from "./DecisionActions";

type ReviewItem = {
  assessment_id: string;
  company_name: string;
  level: number;
  revision: number;
  headline?: string;
  recommendation?: string;
  conditions?: string[];
  claim_total?: number;
  target?: Record<string, unknown>;
  can_decide?: boolean;
  llm_used?: boolean;
};

export default async function DecisionsPage() {
  const cookie = await sessionCookie();
  const status = await apiJson<Record<string, unknown>>("/api/v1/system/status");
  const reviews = cookie
    ? await apiJson<{ items: ReviewItem[]; total?: number }>(
        "/api/v1/reviews?status=pending",
        cookie,
      )
    : null;

  // API returns oldest first — matches home queue copy.
  const items = reviews?.items || [];
  const liveAgent = items.some((r) => Boolean(r.llm_used || r.headline || r.claim_total));

  return (
    <ResearchShell
      title="Decisions"
      pendingDecisions={items.length}
      demo={Boolean(status?.demo_workspace) && !liveAgent}
      mode={String(status?.mode || "")}
    >
      <div className="page-stack">
        <div className="ph">
          <div>
            <h1>Decisions</h1>
            <p className="sub">
              One partner decides. Your decision applies to the report version exactly as you see
              it; it never changes afterwards.
            </p>
          </div>
          {items.length ? (
            <StatusPill color="var(--brand)">{items.length} waiting</StatusPill>
          ) : null}
        </div>

        {!items.length ? (
          <section className="card">
            <div className="ch">
              <h2>Pending</h2>
              <span className="lbl">From agent research</span>
            </div>
            <div className="cb">
              <p className="mute flush">
                Nothing waiting for a decision. When a screen finishes, the agent recommendation
                lands here.
              </p>
            </div>
          </section>
        ) : (
          items.map((r) => {
            const tone = recTone(r.recommendation);
            const shortRec = (r.recommendation || "review").toLowerCase();
            return (
              <section className="card" key={r.assessment_id}>
                <div className="ch">
                  <div className="hstack">
                    <span className="avatar">{avatarLetter(r.company_name)}</span>
                    <div className="vstack">
                      <h2 className="flush">
                        <Link href={`/companies/a/${r.assessment_id}`}>{r.company_name}</Link>
                      </h2>
                      <span className="lbl">
                        L{r.level} · rev {r.revision}
                        {typeof r.claim_total === "number" ? ` · ${r.claim_total} findings` : ""}
                      </span>
                    </div>
                  </div>
                  <StatusPill color={tone} title={recLabel(r.recommendation)}>
                    {shortRec}
                  </StatusPill>
                </div>
                <div className="cb stack">
                  <p className="lede strong">
                    {r.headline || recBlurb(r.recommendation) || "Ready for partner review."}
                  </p>
                  {!!r.conditions?.length && (
                    <ul className="mute mute-sm list-cond">
                      {r.conditions.map((c) => (
                        <li key={c}>{c}</li>
                      ))}
                    </ul>
                  )}
                </div>
                <div className="cf">
                  {r.can_decide && r.target ? (
                    <DecisionActions
                      apiBase={publicApiBase()}
                      assessmentId={r.assessment_id}
                      revision={r.revision}
                      target={r.target as never}
                    />
                  ) : (
                    <p className="mute flush">Waiting for a partner to decide.</p>
                  )}
                  <Link
                    className="btn btn-ghost btn-sm"
                    href={`/companies/a/${r.assessment_id}`}
                    style={{ marginLeft: "auto" }}
                  >
                    Open report
                  </Link>
                </div>
              </section>
            );
          })
        )}
      </div>
    </ResearchShell>
  );
}
