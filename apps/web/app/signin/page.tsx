"use client";

import { useState } from "react";
import { publicApiBase } from "@/lib/api";

export default function SignInPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const publicApi = publicApiBase();

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setMessage(null);
    const res = await fetch(`${publicApi}/api/v1/auth/login`, {
      method: "POST",
      credentials: "include",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      setMessage(`Login failed (${res.status})`);
      return;
    }
    window.location.href = "/";
  }

  async function exploreDemo() {
    const res = await fetch(`${publicApi}/api/v1/auth/demo-session`, {
      method: "POST",
      credentials: "include",
    });
    if (!res.ok) {
      setMessage(`Demo session failed (${res.status})`);
      return;
    }
    window.location.href = "/";
  }

  return (
    <main className="auth-main t-light">
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 24 }}>
        <svg width="36" height="36" viewBox="0 0 28 28" aria-hidden="true">
          <rect width="28" height="28" rx="8" fill="var(--brand)" />
          <path
            d="M8 9.5h12M14 9.5v10"
            stroke="#FFFFFF"
            strokeWidth="2.4"
            strokeLinecap="round"
          />
        </svg>
        <h1 className="brand-hero" style={{ fontSize: 32, margin: 0 }}>
          Thesis
        </h1>
      </div>
      <p className="lede">Sign in with a local account, or explore the demo workspace.</p>
      <section className="card">
        <div className="ch">
          <h2>Sign in</h2>
        </div>
        <form onSubmit={onSubmit} className="cb stack">
          <label className="stack" style={{ gap: 4 }}>
            <span className="lbl">Email</span>
            <input
              className="input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              type="email"
              required
            />
          </label>
          <label className="stack" style={{ gap: 4 }}>
            <span className="lbl">Password</span>
            <input
              className="input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              type="password"
              required
            />
          </label>
          <button className="btn btn-primary" type="submit">
            Sign in
          </button>
          <button className="btn" type="button" onClick={exploreDemo}>
            Explore the demo workspace
          </button>
          {message && <p className="err">{message}</p>}
        </form>
      </section>
    </main>
  );
}
