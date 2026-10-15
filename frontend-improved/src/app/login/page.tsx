import { Suspense } from "react";
import { LoginContent } from "./LoginContent";

/**
 * Static login shell. URL-dependent content (error messages, sent confirmation,
 * next-redirect) is handled by LoginContent via useSearchParams(), wrapped in
 * Suspense so the shell can prerender without Next.js encountering URL data
 * during the static build pass.
 */
export default function LoginPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-[#080D16] px-5 py-12 text-slate-100">
      <section className="w-full max-w-md rounded-2xl border border-slate-800 bg-[#0D1421] p-8 shadow-2xl shadow-black/20">
        <div className="mb-8">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-emerald-400">FinWiseAI</p>
          <h1 className="mt-3 text-2xl font-semibold">Sign in to your workspace</h1>
          <p className="mt-2 text-sm text-slate-400">Smarter Insights. Better Investments.</p>
        </div>
        <Suspense>
          <LoginContent />
        </Suspense>
        <p className="mt-6 text-xs leading-relaxed text-slate-500">
          Your sign-in session is stored in secure, HTTP-only cookies.
        </p>
      </section>
    </main>
  );
}
