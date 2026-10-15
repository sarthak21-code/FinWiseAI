import { NextRequest, NextResponse } from "next/server";
import type { EmailOtpType } from "@supabase/supabase-js";
import { createSupabaseServerClient } from "@/lib/supabase/server";

function safeNextUrl(value: string | null, requestUrl: URL): URL {
  if (!value || !value.startsWith("/") || value.startsWith("//")) {
    return new URL("/", requestUrl);
  }
  const destination = new URL(value, requestUrl);
  return destination.origin === requestUrl.origin
    ? destination
    : new URL("/", requestUrl);
}

function sanitizeErrorMessage(msg: string): string {
  return msg
    .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi, "[email]")
    .replace(/https?:\/\/\S+/gi, "[url]")
    .replace(/\b[A-Za-z0-9_-]{40,}\b/g, "[redacted]");
}

export async function GET(request: NextRequest) {
  const errorParam = request.nextUrl.searchParams.get("error");
  const errorCode = request.nextUrl.searchParams.get("error_code");
  const errorDesc = request.nextUrl.searchParams.get("error_description");

  if (errorParam || errorCode) {
    const safeDesc = sanitizeErrorMessage(errorDesc || "");
    console.error(
      `[FinWiseAI Auth] callback received error from Supabase: error=${errorParam} code=${errorCode} desc=${safeDesc}`,
    );
    if (errorCode === "otp_expired" || safeDesc.toLowerCase().includes("expired")) {
      return NextResponse.redirect(new URL("/login?error=otp-expired", request.url));
    }
    return NextResponse.redirect(new URL("/login?error=sign-in", request.url));
  }

  const code = request.nextUrl.searchParams.get("code");
  const tokenHash = request.nextUrl.searchParams.get("token_hash");
  const type = request.nextUrl.searchParams.get("type") as EmailOtpType | null;

  const supabase = await createSupabaseServerClient();

  if (tokenHash && type) {
    const { error } = await supabase.auth.verifyOtp({ token_hash: tokenHash, type });
    if (error) {
      const safeMessage = sanitizeErrorMessage(error.message || "");
      console.error(
        `[FinWiseAI Auth] verifyOtp failed: status=${error.status} code=${error.code} message=${safeMessage}`,
      );
      if (error.code === "otp_expired" || safeMessage.toLowerCase().includes("expired")) {
        return NextResponse.redirect(new URL("/login?error=otp-expired", request.url));
      }
      return NextResponse.redirect(new URL("/login?error=sign-in", request.url));
    }
    return NextResponse.redirect(
      safeNextUrl(request.nextUrl.searchParams.get("next"), request.nextUrl),
    );
  }

  if (code) {
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    if (error) {
      const safeMessage = sanitizeErrorMessage(error.message || "");
      console.error(
        `[FinWiseAI Auth] exchangeCodeForSession failed: status=${error.status} code=${error.code} message=${safeMessage}`,
      );
      if (error.code === "otp_expired" || safeMessage.toLowerCase().includes("expired")) {
        return NextResponse.redirect(new URL("/login?error=otp-expired", request.url));
      }
      return NextResponse.redirect(new URL("/login?error=sign-in", request.url));
    }
    return NextResponse.redirect(
      safeNextUrl(request.nextUrl.searchParams.get("next"), request.nextUrl),
    );
  }

  return NextResponse.redirect(new URL("/login?error=sign-in", request.url));
}
