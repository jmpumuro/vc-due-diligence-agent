import { NextRequest, NextResponse } from "next/server";

const SESSION = "thesis_session";

function apiOrigin() {
  return (
    process.env.INTERNAL_API_URL ||
    process.env.PUBLIC_API_URL ||
    "http://localhost:8001"
  ).replace(/\/$/, "");
}

export async function middleware(req: NextRequest) {
  // Skip static assets and the BFF itself (BFF already forwards Set-Cookie).
  const { pathname } = req.nextUrl;
  if (
    pathname.startsWith("/_next") ||
    pathname.startsWith("/api/") ||
    pathname.includes(".")
  ) {
    return NextResponse.next();
  }

  if (req.cookies.get(SESSION)?.value) {
    return NextResponse.next();
  }

  const res = NextResponse.next();
  try {
    const upstream = await fetch(`${apiOrigin()}/api/v1/auth/demo-session`, {
      method: "POST",
      cache: "no-store",
    });
    if (!upstream.ok) return res;
    const raw = upstream.headers.getSetCookie?.() ?? [];
    let value: string | null = null;
    if (raw.length) {
      value = raw[0].match(new RegExp(`^${SESSION}=([^;]+)`))?.[1] ?? null;
    }
    if (!value) {
      const single = upstream.headers.get("set-cookie");
      value = single?.match(new RegExp(`^${SESSION}=([^;]+)`))?.[1] ?? null;
    }
    if (value) {
      res.cookies.set(SESSION, value, {
        httpOnly: true,
        path: "/",
        sameSite: "lax",
        maxAge: 60 * 60 * 4,
      });
    }
  } catch {
    // Demo mint is best-effort; pages still fall back to sessionCookie().
  }
  return res;
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
