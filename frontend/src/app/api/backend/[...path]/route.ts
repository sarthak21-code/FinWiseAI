import { NextResponse } from "next/server";

type RouteContext = {
  params: Promise<{
    path: string[];
  }>;
};

export async function GET(
  _request: Request,
  context: RouteContext,
) {
  const { path } = await context.params;

  const backendBase = (
    process.env.BACKEND_URL ?? "http://127.0.0.1:8000"
  ).replace(/\/+$/, "");

  const encodedPath = path
    .map((segment) => encodeURIComponent(segment))
    .join("/");

  try {
    const upstream = await fetch(
      `${backendBase}/${encodedPath}`,
      {
        cache: "no-store",
        headers: {
          Accept: "application/json",
        },
      },
    );

    const body = await upstream.text();

    return new Response(body, {
      status: upstream.status,
      headers: {
        "Content-Type":
          upstream.headers.get("content-type") ??
          "application/json",
        "Cache-Control": "no-store",
      },
    });
  } catch {
    return NextResponse.json(
      {
        detail:
          `Cannot connect to the VantageAI backend at ${backendBase}. ` +
          "Ensure FastAPI is running on port 8000 and try again.",
      },
      { status: 502 },
    );
  }
}
