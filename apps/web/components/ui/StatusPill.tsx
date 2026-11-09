import type { ReactNode } from "react";

/** Shared status chip — uses `--c` so light/dark tokens stay consistent. */
export default function StatusPill({
  color = "var(--gray)",
  children,
  title,
}: {
  color?: string;
  children: ReactNode;
  title?: string;
}) {
  return (
    <span className="pill" title={title} style={{ ["--c" as string]: color }}>
      <span className="dot" style={{ background: color }} />
      {children}
    </span>
  );
}
