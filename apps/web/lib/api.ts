const API =
  process.env.INTERNAL_API_URL || process.env.PUBLIC_API_URL || "http://localhost:8001";

export function apiBase() {
  return API.replace(/\/$/, "");
}

/**
 * Base URL for browser / client components.
 * Empty string = same-origin `/api/v1/*` via the Next BFF proxy
 * (`app/api/v1/[...path]/route.ts`). Avoids cross-origin EventSource
 * cookie failures between :3000 and :8001.
 */
export function publicApiBase() {
  return "";
}

export async function apiGet(path: string, cookie?: string | null) {
  const headers: HeadersInit = {};
  if (cookie) headers.cookie = cookie;
  return fetch(`${apiBase()}${path}`, { cache: "no-store", headers });
}

export async function apiJson<T = unknown>(
  path: string,
  cookie?: string | null,
): Promise<T | null> {
  const res = await apiGet(path, cookie);
  if (!res.ok) return null;
  return (await res.json()) as T;
}
