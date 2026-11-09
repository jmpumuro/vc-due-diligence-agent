"use client";

import { useState } from "react";
import { publicApiBase } from "@/lib/api";
import { ensureDemoSession } from "@/lib/demo-session";

type Entry = {
  id: string;
  company_name: string;
  primary_domain?: string | null;
  cadence: string;
  paused: boolean;
};

export default function WatchlistClient({ initial }: { initial: Entry[] }) {
  const [items, setItems] = useState(initial);
  const [name, setName] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const api = publicApiBase();

  async function add(e: React.FormEvent) {
    e.preventDefault();
    await ensureDemoSession(api);
    const res = await fetch(`${api}/api/v1/watchlist`, {
      method: "POST",
      credentials: "include",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ company_name: name, cadence: "weekly" }),
    });
    if (!res.ok) {
      setMsg(`Failed (${res.status})`);
      return;
    }
    const body = await res.json();
    setItems((prev) => [
      { id: body.id, company_name: body.company_name, cadence: "weekly", paused: false },
      ...prev,
    ]);
    setName("");
  }

  async function toggle(id: string, paused: boolean) {
    await ensureDemoSession(api);
    const res = await fetch(`${api}/api/v1/watchlist/${id}`, {
      method: "PATCH",
      credentials: "include",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ paused: !paused }),
    });
    if (!res.ok) return;
    setItems((prev) => prev.map((x) => (x.id === id ? { ...x, paused: !paused } : x)));
  }

  async function reassess(id: string) {
    setMsg(null);
    await ensureDemoSession(api);
    const res = await fetch(`${api}/api/v1/watchlist/${id}/reassess`, {
      method: "POST",
      credentials: "include",
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      setMsg(String(body.detail || `Reassess failed (${res.status})`));
      return;
    }
    setMsg("Reassess queued.");
  }

  return (
    <>
      <div className="ph">
        <div>
          <h1>Watchlist</h1>
          <p className="sub">
            We keep an eye on these companies and tell you when something important changes.
          </p>
        </div>
      </div>

      <section className="card" style={{ maxWidth: 480 }}>
        <div className="ch">
          <h2>Add company</h2>
          <span className="lbl">Funding, launches, hiring, sanctions lists</span>
        </div>
        <form className="cb stack" onSubmit={add}>
          <input
            className="input"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Company name"
            required
          />
          <button className="btn btn-primary" type="submit">
            Watch
          </button>
          {msg && <p className="err">{msg}</p>}
        </form>
      </section>

      <section className="card">
        <div className="ch">
          <h2>Watching</h2>
          <span className="lbl">{items.length}</span>
        </div>
        {!items.length ? (
          <div className="cb">
            <p className="mute" style={{ margin: 0 }}>
              Watchlist is empty.
            </p>
          </div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Company</th>
                <th>Cadence</th>
                <th>Status</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {items.map((e) => (
                <tr key={e.id}>
                  <td>{e.company_name}</td>
                  <td>{e.cadence}</td>
                  <td>
                    <span className="pill">
                      <span
                        className="dot"
                        style={{ background: e.paused ? "var(--gray)" : "var(--green)" }}
                      />
                      {e.paused ? "Paused" : "Active"}
                    </span>
                  </td>
                  <td>
                    <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                      <button
                        className="btn btn-ghost"
                        type="button"
                        disabled={e.paused}
                        onClick={() => reassess(e.id)}
                      >
                        Reassess
                      </button>
                      <button
                        className="btn btn-ghost"
                        type="button"
                        onClick={() => toggle(e.id, e.paused)}
                      >
                        {e.paused ? "Resume" : "Pause"}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </>
  );
}
