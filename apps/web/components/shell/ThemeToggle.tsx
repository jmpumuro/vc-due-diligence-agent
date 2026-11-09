"use client";

import { useEffect, useState } from "react";

export type ThesisTheme = "light" | "dark";

export function applyTheme(next: ThesisTheme) {
  const root = document.documentElement;
  root.dataset.theme = next;
  root.classList.toggle("t-dark", next === "dark");
  root.classList.toggle("t-light", next === "light");
  root.style.colorScheme = next;
}

export function readStoredTheme(): ThesisTheme {
  const saved = window.localStorage.getItem("thesis-theme");
  if (saved === "dark" || saved === "light") return saved;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export default function ThemeToggle() {
  const [theme, setTheme] = useState<ThesisTheme>("light");

  useEffect(() => {
    const next = readStoredTheme();
    setTheme(next);
    applyTheme(next);
  }, []);

  function toggle() {
    const next: ThesisTheme = theme === "dark" ? "light" : "dark";
    setTheme(next);
    window.localStorage.setItem("thesis-theme", next);
    applyTheme(next);
  }

  return (
    <button
      type="button"
      className="iconbtn"
      aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
      aria-pressed={theme === "dark"}
      title={theme === "dark" ? "Light theme" : "Dark theme"}
      onClick={toggle}
    >
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
        {theme === "dark" ? (
          <path d="M12 3v2M12 19v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M3 12h2M19 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4M12 8a4 4 0 1 1 0 8 4 4 0 0 1 0-8z" />
        ) : (
          <path d="M21 14.5A8.5 8.5 0 1 1 9.5 3 7 7 0 0 0 21 14.5z" />
        )}
      </svg>
    </button>
  );
}
