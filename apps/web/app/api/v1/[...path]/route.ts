import { NextRequest } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function upstreamBase() {
  return (
    process.env.INTERNAL_API_URL ||
    process.env.PUBLIC_API_URL ||
    "http://localhost:8001"
  ).replace(/\/$/, "");
}

async function proxy(req: NextRequest, path: string[]) {
  const target = `${upstreamBase()}/api/v1/${path.join("/")}${req.nextUrl.search}`;
  const headers = new Headers();
  const cookie = req.headers.get("cookie");
  if (cookie) headers.set("cookie", cookie);
  const accept = req.headers.get("accept");
  if (accept) headers.set("accept", accept);
  const lastEventId = req.headers.get("last-event-id");
  if (lastEventId) headers.set("last-event-id", lastEventId);
  const contentType = req.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  const idem = req.headers.get("idempotency-key");
  if (idem) headers.set("idempotency-key", idem);

  const init: RequestInit & { duplex?: "half" } = {
    method: req.method,
    headers,
    cache: "no-store",
    redirect: "manual",
  };
  if (req.method !== "GET" && req.method !== "HEAD") {
    init.body = req.body;
    init.duplex = "half";
  }

  const upstream = await fetch(target, init);
  const out = new Headers();
  for (const key of [
    "content-type",
    "cache-control",
    "connection",
    "x-accel-buffering",
  ]) {
    const value = upstream.headers.get(key);
    if (value) out.set(key, value);
  }
  const setCookies =
    typeof upstream.headers.getSetCookie === "function"
      ? upstream.headers.getSetCookie()
      : [];
  if (setCookies.length) {
    for (const c of setCookies) out.append("set-cookie", c);
  } else {
    const single = upstream.headers.get("set-cookie");
    if (single) out.set("set-cookie", single);
  }

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: out,
  });
}

type Ctx = { params: Promise<{ path: string[] }> };

export async function GET(req: NextRequest, ctx: Ctx) {
  const { path } = await ctx.params;
  return proxy(req, path);
}

export async function POST(req: NextRequest, ctx: Ctx) {
  const { path } = await ctx.params;
  return proxy(req, path);
}

export async function PATCH(req: NextRequest, ctx: Ctx) {
  const { path } = await ctx.params;
  return proxy(req, path);
}

export async function PUT(req: NextRequest, ctx: Ctx) {
  const { path } = await ctx.params;
  return proxy(req, path);
}

export async function DELETE(req: NextRequest, ctx: Ctx) {
  const { path } = await ctx.params;
  return proxy(req, path);
}
