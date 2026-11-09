import ConsoleShell from "@/components/shell/ConsoleShell";
import { apiBase, apiJson } from "@/lib/api";

export default async function HealthPage() {
  const status = await apiJson<Record<string, unknown>>("/api/v1/system/status");
  let readyOk = false;
  let readyBody: Record<string, unknown> | null = null;
  try {
    const readyRes = await fetch(`${apiBase()}/health/ready`, { cache: "no-store" });
    readyOk = readyRes.ok;
    readyBody = readyRes.ok ? ((await readyRes.json()) as Record<string, unknown>) : null;
  } catch {
    readyOk = false;
  }

  const search = (status?.search as Record<string, unknown>) || {};
  const provider = (status?.provider as Record<string, unknown>) || {};
  const ofac = (status?.ofac as Record<string, unknown>) || {};
  const deps = (status?.dependencies as Record<string, unknown>) || {};
  const objectStore = (deps.object_store as Record<string, unknown>) || {};
  const localRoute = (provider.local_route as Record<string, unknown>) || {};
  const privatePipeline = (status?.private_pipeline as Record<string, unknown>) || {};
  const mode = String(status?.mode || "—");
  const clamOk = Boolean(privatePipeline.clamav);
  const docsOk = Boolean(privatePipeline.worker_docs);
  const degraded =
    !readyOk || mode === "degraded" || mode === "setup_required" || !clamOk || !docsOk;

  return (
    <ConsoleShell title="Health" mode={status?.mode as string | undefined}>
      <div className="ph">
        <div>
          <h1>Health</h1>
          <p className="sub">Dependency and remediation status.</p>
        </div>
      </div>
      <section className="card">
        <div className="ch">
          <h2>Dependencies</h2>
          <span className="pill">
            <span
              className="dot"
              style={{ background: degraded ? "var(--amber)" : "var(--green)" }}
            />
            {degraded ? "API degraded / not ready" : "API ready"}
          </span>
        </div>
        <div className="row">
          <span>Mode</span>
          <span>{mode}</span>
        </div>
        <div className="row">
          <span>Ready probe</span>
          <span>{readyOk ? "ok" : "failed"}</span>
        </div>
        <div className="row">
          <span>Setup</span>
          <span>{String(status?.setup_complete)}</span>
        </div>
        <div className="row">
          <span>SearXNG</span>
          <span>
            {String(search.state || "—")}
            {typeof search.result_count === "number"
              ? ` · ${search.result_count} results`
              : ""}
            {Array.isArray(search.engines_responding) && search.engines_responding.length
              ? ` · ok:${(search.engines_responding as string[]).join(",")}`
              : ""}
            {Array.isArray(search.engines_failed) && search.engines_failed.length
              ? ` · failed:${(search.engines_failed as string[]).slice(0, 4).join(",")}`
              : ""}
          </span>
        </div>
        <div className="row">
          <span>Object store</span>
          <span>{objectStore.ok ? "ok" : String(objectStore.error || "—")}</span>
        </div>
        <div className="row">
          <span>Agent route (public)</span>
          <span>
            {String(provider.state || "—")}
            {provider.model ? ` · ${String(provider.model)}` : ""}
          </span>
        </div>
        <div className="row">
          <span>OFAC datasets</span>
          <span>
            {ofac.status
              ? `${String(ofac.status)} · ${String(ofac.mode || "")} · ${String(ofac.record_count ?? "—")} records`
              : "unavailable"}
          </span>
        </div>
        <div className="row">
          <span>Local agent route</span>
          <span>
            {provider.local_route_available
              ? "route available"
              : String(localRoute.reason || "not configured (fail-closed for private)")}
          </span>
        </div>
        <div className="row">
          <span>ClamAV</span>
          <span>{clamOk ? "ok" : "unavailable / starting"}</span>
        </div>
        <div className="row">
          <span>worker-docs</span>
          <span>
            {docsOk ? "ok" : "unavailable"}
            {privatePipeline.tesseract ? ` · ${String(privatePipeline.tesseract)}` : ""}
          </span>
        </div>
        <div className="row">
          <span>OCR parse (harness)</span>
          <span>
            {privatePipeline.ocr_parse_available
              ? "available"
              : "unavailable"}
            {(() => {
              const harness = privatePipeline.harness_self_test as
                | Record<string, unknown>
                | undefined;
              if (!harness) return "";
              return harness.ok
                ? ` · self-test ok · ${String(harness.page_count ?? "—")} pages`
                : ` · self-test ${String(harness.error || "failed")}`;
            })()}
          </span>
        </div>
        <div className="row">
          <span>OCR product Verified</span>
          <span className="mute">
            {privatePipeline.ocr_verified ? "ok" : "open (q.docs / D4 Verified ≠ health)"}
          </span>
        </div>
        <div className="row">
          <span>L3 upload</span>
          <span>
            {privatePipeline.upload_enabled ? "ClamAV-gated enabled" : "SCANNER_UNAVAILABLE"}
            {privatePipeline.notice ? ` · ${String(privatePipeline.notice)}` : ""}
          </span>
        </div>
        <div className="row">
          <span>L3 screening</span>
          <span className="mute">
            {privatePipeline.level3_screening ? "enabled" : "fail-closed (LEVEL3_PRIVATE_PIPELINE_NOT_READY)"}
          </span>
        </div>
        {readyBody?.demo_workspace != null && (
          <div className="row">
            <span>Demo workspace</span>
            <span>{String(readyBody.demo_workspace)}</span>
          </div>
        )}
      </section>
    </ConsoleShell>
  );
}
