"use client";

import { useCallback, useRef, useState } from "react";
import { ensureDemoSession } from "@/lib/demo-session";

type PrivateDoc = {
  document_id: string;
  filename: string;
  status: string;
  byte_size?: number;
  ocr_pages?: number | null;
  scan_detail?: string | null;
};

export default function DataRoomUpload({
  apiBase,
  assessmentId,
  uploadEnabled,
  notice,
  initialDocs = [],
}: {
  apiBase: string;
  assessmentId: string;
  uploadEnabled: boolean;
  notice?: string;
  initialDocs?: PrivateDoc[];
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [docs, setDocs] = useState<PrivateDoc[]>(initialDocs);
  const [busy, setBusy] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    await ensureDemoSession(apiBase);
    const res = await fetch(`${apiBase}/api/v1/assessments/${assessmentId}/documents`, {
      credentials: "include",
      cache: "no-store",
    });
    if (!res.ok) return;
    const body = (await res.json()) as { items?: PrivateDoc[] };
    setDocs(body.items || []);
  }, [apiBase, assessmentId]);

  async function uploadFile(file: File) {
    setBusy(true);
    setMessage(null);
    try {
      await ensureDemoSession(apiBase);
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${apiBase}/api/v1/assessments/${assessmentId}/documents`, {
        method: "POST",
        credentials: "include",
        body: form,
      });
      if (!res.ok) {
        let detail = `HTTP ${res.status}`;
        try {
          const err = (await res.json()) as { detail?: string };
          detail = err.detail || detail;
        } catch {
          /* ignore */
        }
        setMessage(detail);
        return;
      }
      const body = (await res.json()) as { notice?: string };
      setMessage(body.notice || "Uploaded.");
      await refresh();
    } catch (exc) {
      setMessage(exc instanceof Error ? exc.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  function onFiles(list: FileList | null) {
    const file = list?.[0];
    if (!file) return;
    void uploadFile(file);
  }

  return (
    <section className="card">
      <div className="ch">
        <h2>Private uploads</h2>
        <span className="pill">
          <span
            className="dot"
            style={{ background: uploadEnabled ? "var(--green)" : "var(--amber)" }}
          />
          {uploadEnabled ? "ClamAV ready" : "scanner unavailable"}
        </span>
      </div>
      <div className="cb stack">
        {notice ? <p className="mute" style={{ margin: 0 }}>{notice}</p> : null}
        <div
          role="button"
          tabIndex={0}
          className="dropzone"
          style={{
            border: `1px dashed ${dragOver ? "var(--brand)" : "var(--border)"}`,
            borderRadius: 10,
            padding: "28px 18px",
            textAlign: "center",
            background: dragOver ? "var(--brand-soft)" : "transparent",
            cursor: uploadEnabled && !busy ? "pointer" : "not-allowed",
            opacity: uploadEnabled ? 1 : 0.55,
          }}
          onClick={() => uploadEnabled && !busy && inputRef.current?.click()}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              if (uploadEnabled && !busy) inputRef.current?.click();
            }
          }}
          onDragOver={(e) => {
            e.preventDefault();
            if (uploadEnabled) setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            if (!uploadEnabled || busy) return;
            onFiles(e.dataTransfer.files);
          }}
        >
          <div style={{ fontWeight: 600, marginBottom: 6 }}>
            {busy ? "Scanning and parsing…" : "Drop a PDF here, or click to choose"}
          </div>
          <div className="mute" style={{ fontSize: 13 }}>
            Fail-closed malware scan · PDF native/OCR parse · private AI stays off
          </div>
          <input
            ref={inputRef}
            type="file"
            accept=".pdf,application/pdf"
            hidden
            disabled={!uploadEnabled || busy}
            onChange={(e) => onFiles(e.target.files)}
          />
        </div>
        {message ? <p className={message.includes("UNAVAILABLE") || message.includes("MALWARE") ? "err" : "mute"}>{message}</p> : null}
      </div>
      {!docs.length ? (
        <div className="row">
          <span>Documents</span>
          <span className="mute">none yet</span>
        </div>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>File</th>
              <th>Status</th>
              <th>OCR pages</th>
              <th>Size</th>
            </tr>
          </thead>
          <tbody>
            {docs.map((d) => (
              <tr key={d.document_id}>
                <td>{d.filename}</td>
                <td>
                  <span className="pill">
                    <span
                      className="dot"
                      style={{
                        background:
                          d.status === "quarantined" || d.status === "parse_failed"
                            ? "var(--red)"
                            : "var(--green)",
                      }}
                    />
                    {d.status}
                  </span>
                </td>
                <td>{d.ocr_pages ?? "—"}</td>
                <td className="mute">
                  {typeof d.byte_size === "number" ? `${Math.round(d.byte_size / 1024)} KB` : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
