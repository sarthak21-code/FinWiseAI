import { createServerClient } from "@supabase/ssr";
import { NextRequest, NextResponse } from "next/server";

const isPublicPath = (pathname: string) =>
  pathname === "/login" || pathname.startsWith("/auth/callback");

export async function proxy(request: NextRequest) {
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const publishableKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
  if (!supabaseUrl || !publishableKey) {
    if (isPublicPath(request.nextUrl.pathname)) return NextResponse.next();
    if (request.nextUrl.pathname.startsWith("/api/backend/")) {
      return NextResponse.json(
        { detail: "Authentication is not configured." },
        { status: 503, headers: { "Cache-Control": "no-store" } },
      );
    }
    return NextResponse.redirect(new URL("/login?error=auth-config", request.url));
  }

  let response = NextResponse.next({ request });
  const supabase = createServerClient(supabaseUrl, publishableKey, {
    cookieOptions: {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
    },
    cookies: {
      getAll: () => request.cookies.getAll(),
      setAll(cookiesToSet) {
        cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value));
        response = NextResponse.next({ request });
        cookiesToSet.forEach(({ name, value, options }) =>
          response.cookies.set(name, value, options),
        );
      },
    },
  });

  const { data, error } = await supabase.auth.getClaims();
  const isApi = request.nextUrl.pathname.startsWith("/api/backend/");
  if (error || !data?.claims?.sub) {
    if (isPublicPath(request.nextUrl.pathname)) return response;
    if (isApi) {
      return NextResponse.json(
        { detail: "Authentication required." },
        { status: 401, headers: { "Cache-Control": "no-store" } },
      );
    }
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set(
      "next",
      `${request.nextUrl.pathname}${request.nextUrl.search}`,
    );
    const redirect = NextResponse.redirect(loginUrl);
    redirect.headers.set("Cache-Control", "no-store");
    response.cookies.getAll().forEach((cookie) => redirect.cookies.set(cookie));
    return redirect;
  }

  if (request.nextUrl.pathname === "/login") {
    return NextResponse.redirect(new URL("/", request.url));
  }
  return response;
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|icon.svg|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
