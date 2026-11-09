/**
 * Client-side demo session bootstrap for cookie-backed API calls.
 * No-op when a session cookie already exists (API still accepts the POST).
 */
export async function ensureDemoSession(apiBase = ""): Promise<void> {
  await fetch(`${apiBase}/api/v1/auth/demo-session`, {
    method: "POST",
    credentials: "include",
  });
}
