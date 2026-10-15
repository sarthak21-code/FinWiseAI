"use client";

import { useSearchParams } from "next/navigation";
import { requestSignIn } from "./actions";

const errors: Record<string, string> = {
  "invalid-email": "Enter a valid email address.",
  "auth-config": "Authentication is not configured for this deployment.",
  "sign-in": "We could not start sign-in. Please try again.",
  "rate-limit": "Email rate limit reached. Please wait a minute before requesting another link.",
  "otp-expired": "This sign-in link is invalid or has expired. Please request a new one.",
};

/**
 * Reads URL search params on the client so the static login shell can be
 * prerendered without Next.js encountering URL data during the build pass.
 * Must be wrapped in <Suspense> by the parent page.
 */
export function LoginContent() {
  const searchParams = useSearchParams();
  const message = searchParams.get("error")
    ? errors[searchParams.get("error")!]
    : undefined;
  const sent = searchParams.get("sent");
  const next = searchParams.get("next") ?? "";

  return sent ? (
    <p
      role="status"
      className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-4 text-sm text-emerald-200"
    >
      If this address can sign in, a secure link is on its way. Check your
      inbox.
    </p>
  ) : (
    <form action={requestSignIn} className="space-y-4">
      <input type="hidden" name="next" value={next} />
      <label
        htmlFor="email"
        className="block text-sm font-medium text-slate-300"
      >
        Email address
      </label>
      <input
        id="email"
        name="email"
        type="email"
        autoComplete="email"
        required
        className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2.5 text-sm outline-none focus:border-emerald-500"
      />
      {message && (
        <p role="alert" className="text-sm text-rose-300">
          {message}
        </p>
      )}
      <button className="w-full rounded-lg bg-emerald-500 px-4 py-2.5 text-sm font-semibold text-slate-950 transition hover:bg-emerald-400">
        Email me a sign-in link
      </button>
    </form>
  );
}
