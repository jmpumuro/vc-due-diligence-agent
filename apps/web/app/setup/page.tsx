"use client";

import { useState } from "react";
import { ThesisMark } from "@/components/shell/marks";
import { publicApiBase } from "@/lib/api";

export default function SetupPage() {
  const [token, setToken] = useState("");
  const [firmName, setFirmName] = useState("");
  const [ownerName, setOwnerName] = useState("");
  const [ownerEmail, setOwnerEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [ok, setOk] = useState(false);
  const publicApi = publicApiBase();

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setMessage(null);
    setOk(false);
    const res = await fetch(`${publicApi}/api/v1/setup`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        token,
        firm_name: firmName,
        owner_name: ownerName,
        owner_email: ownerEmail,
        password,
      }),
    });
    if (!res.ok) {
      const body = await res.text();
      setMessage(`Setup failed (${res.status}): ${body}`);
      return;
    }
    setOk(true);
    setMessage("Owner created. You can sign in.");
    window.setTimeout(() => {
      window.location.href = "/signin";
    }, 800);
  }

  return (
    <main className="auth-main t-light">
      <div className="hstack" style={{ gap: 12, marginBottom: 24 }}>
        <ThesisMark />
        <h1 className="brand-hero flush" style={{ fontSize: 32 }}>
          Thesis
        </h1>
      </div>
      <p className="lede">
        First-run setup. Paste the one-time token from the API container logs (
        <code className="mono">SETUP REQUIRED</code>).
      </p>
      <section className="card">
        <div className="ch">
          <h2>Create owner</h2>
        </div>
        <form onSubmit={onSubmit} className="cb stack">
          <label className="stack" style={{ gap: 4 }}>
            <span className="lbl">Setup token</span>
            <input
              className="input"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              required
            />
          </label>
          <label className="stack" style={{ gap: 4 }}>
            <span className="lbl">Firm name</span>
            <input
              className="input"
              value={firmName}
              onChange={(e) => setFirmName(e.target.value)}
              required
            />
          </label>
          <label className="stack" style={{ gap: 4 }}>
            <span className="lbl">Owner name</span>
            <input
              className="input"
              value={ownerName}
              onChange={(e) => setOwnerName(e.target.value)}
              required
            />
          </label>
          <label className="stack" style={{ gap: 4 }}>
            <span className="lbl">Owner email</span>
            <input
              className="input"
              value={ownerEmail}
              onChange={(e) => setOwnerEmail(e.target.value)}
              type="email"
              required
            />
          </label>
          <label className="stack" style={{ gap: 4 }}>
            <span className="lbl">Password (min 10)</span>
            <input
              className="input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              type="password"
              minLength={10}
              required
            />
          </label>
          <button type="submit" className="btn btn-primary">
            Create firm
          </button>
          {message ? <p className={ok ? "mute flush" : "err flush"}>{message}</p> : null}
        </form>
      </section>
    </main>
  );
}
