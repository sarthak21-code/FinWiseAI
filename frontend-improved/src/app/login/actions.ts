"use server";

import { redirect } from "next/navigation";
import { createSupabaseServerClient } from "@/lib/supabase/server";

export async function requestSignIn(formData: FormData) {
  const email = String(formData.get("email") ?? "").trim().toLowerCase();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    redirect("/login?error=invalid-email");
  }

  const configuredSiteUrl = process.env.NEXT_PUBLIC_SITE_URL;
  if (!configuredSiteUrl) redirect("/login?error=auth-config");

  let callbackUrl: string;
  try {
    const siteUrl = new URL(configuredSiteUrl);
    if (process.env.NODE_ENV === "production" && siteUrl.protocol !== "https:") {
      throw new Error("Production sign-in requires HTTPS.");
    }
    const next = String(formData.get("next") ?? "");
    const callback = new URL("/auth/callback", siteUrl);
    if (next.startsWith("/") && !next.startsWith("//")) {
      callback.searchParams.set("next", next);
    }
    callbackUrl = callback.toString();
  } catch {
    redirect("/login?error=auth-config");
  }

  const supabase = await createSupabaseServerClient();
  const { error } = await supabase.auth.signInWithOtp({
    email,
    options: { emailRedirectTo: callbackUrl },
  });

  if (error) {
    const safeMessage = (error.message || "")
      .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi, "[email]")
      .replace(/https?:\/\/\S+/gi, "[url]")
      .replace(/\b[A-Za-z0-9_-]{40,}\b/g, "[redacted]");

    console.error(
      `[FinWiseAI Auth] signInWithOtp failed: name=${error.name} status=${error.status} code=${error.code} message=${safeMessage}`,
    );

    const isRateLimit =
      error.status === 429 ||
      error.code === "over_email_send_rate_limit" ||
      safeMessage.toLowerCase().includes("rate limit") ||
      safeMessage.toLowerCase().includes("60 seconds");

    if (isRateLimit) {
      redirect("/login?error=rate-limit");
    }

    redirect("/login?error=sign-in");
  }

  redirect("/login?sent=1");
}
