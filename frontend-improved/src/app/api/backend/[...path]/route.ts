import { NextResponse } from "next/server";

type RouteContext = {
  params: Promise<{
    path: string[];
  }>;
};

import { getAuthenticatedAccessToken } from "@/lib/supabase/server";

async function proxyRequest(
  request: Request,
  context: RouteContext,
): Promise<Response> {
  const origin = request.headers.get("origin");
  if (request.method !== "GET" && origin !== new URL(request.url).origin) {
    return NextResponse.json(
      { detail: "Cross-origin request denied." },
      { status: 403, headers: { "Cache-Control": "no-store" } },
    );
  }

  let accessToken: string | null;
  try {
    accessToken = await getAuthenticatedAccessToken();
  } catch {
    accessToken = null;
  }
  if (!accessToken) {
    return NextResponse.json(
      { detail: "Authentication required." },
      { status: 401, headers: { "Cache-Control": "no-store" } },
    );
  }

  const { path } = await context.params;

  const backendBase = (
    process.env.BACKEND_URL ?? "http://127.0.0.1:8000"
  ).replace(/\/+$/, "");

  const encodedPath = path
    .map((segment) => encodeURIComponent(segment))
    .join("/");

  try {
    const targetUrl = new URL(`${backendBase}/${encodedPath}`);
    targetUrl.search = new URL(request.url).search;

    // Forward only the verified session bearer token and JSON headers. Never pass
    // browser cookies or arbitrary client-provided identity/hop-by-hop headers.
    const headers = new Headers({ Accept: "application/json" });
    headers.set("Authorization", `Bearer ${accessToken}`);
    const contentType = request.headers.get("content-type");
    if (contentType) {
      headers.set("Content-Type", contentType);
    }

    const body = request.method === "GET" || request.body === null
      ? undefined
      : await request.arrayBuffer();

    const upstream = await fetch(
      targetUrl,
      {
        method: request.method,
        body,
        cache: "no-store",
        headers,
      },
    );

    const responseBody = [204, 205, 304].includes(upstream.status)
      ? null
      : await upstream.arrayBuffer();
    const responseHeaders = new Headers({ "Cache-Control": "no-store" });
    for (const name of ["content-type", "retry-after", "www-authenticate"]) {
      const value = upstream.headers.get(name);
      if (value) {
        responseHeaders.set(name, value);
      }
    }

    return new Response(responseBody, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers: responseHeaders,
    });
  } catch {
    return NextResponse.json(
      {
        detail: "Cannot connect to the FinWiseAI analysis service. " +
          "Ensure FastAPI is running and try again.",
      },
      { status: 502 },
    );
  }
}

export async function GET(request: Request, context: RouteContext) {
  return proxyRequest(request, context);
}

export async function POST(request: Request, context: RouteContext) {
  return proxyRequest(request, context);
}
