import { cookies } from "next/headers";
import { apiBase } from "@/lib/api";

const SESSION = "thesis_session";

/**
 * Prefer the browser's existing session for SSR. Only mint a demo session when
 * absent, and mirror it onto the Next response so client widgets share it.
 * Server Components only — do not import from client components.
 */
export async function sessionCookie(): Promise<string | null> {
  const jar = await cookies();
  const existing = jar.get(SESSION)?.value;
  if (existing) {
    return `${SESSION}=${existing}`;
  }

  const res = await fetch(`${apiBase()}/api/v1/auth/demo-session`, {
    method: "POST",
    cache: "no-store",
  });
  if (!res.ok) return null;

  let value: string | null = null;
  const raw = res.headers.getSetCookie?.() ?? [];
  if (raw.length) {
    const match = raw[0].match(new RegExp(`^${SESSION}=([^;]+)`));
    value = match?.[1] ?? null;
  }
  if (!value) {
    const single = res.headers.get("set-cookie");
    const match = single?.match(new RegExp(`^${SESSION}=([^;]+)`));
    value = match?.[1] ?? null;
  }
  if (!value) return null;

  try {
    jar.set(SESSION, value, {
      httpOnly: true,
      path: "/",
      sameSite: "lax",
      maxAge: 60 * 60 * 4,
    });
  } catch {
    // cookies().set can throw outside a mutable request context
  }
  return `${SESSION}=${value}`;
}
