import React from "react";
import { friendlyStatus, statusClasses } from "@/lib/formatting";

export function StatusBadge({ status }: { status: string }) {
  const norm = status?.toLowerCase() || "unavailable";
  const dotColor =
    norm === "bullish"
      ? "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.5)]"
      : norm === "bearish"
        ? "bg-rose-400 shadow-[0_0_8px_rgba(248,113,113,0.5)]"
        : norm === "neutral"
          ? "bg-amber-300"
          : norm === "insufficient_data"
            ? "bg-orange-400"
            : "bg-slate-400";

  return (
    <span
      className={`inline-flex items-center gap-2 rounded-md border px-2.5 py-1 text-[11px] font-bold uppercase tracking-wider ${statusClasses(
        norm,
      )}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${dotColor}`} />
      <span>{friendlyStatus(norm)}</span>
    </span>
  );
}

export function MetricCard({
  label,
  value,
  subtext,
  icon,
  tone = "neutral",
}: {
  label: string;
  value: string;
  subtext?: string;
  icon?: React.ReactNode;
  tone?: "positive" | "negative" | "warning" | "neutral";
}) {
  const toneBg =
    tone === "positive"
      ? "border-emerald-500/20 bg-emerald-500/5"
      : tone === "negative"
        ? "border-rose-500/20 bg-rose-500/5"
        : tone === "warning"
          ? "border-amber-500/20 bg-amber-500/5"
          : "border-slate-800 bg-[#111B2B]/60";

  const valColor =
    tone === "positive"
      ? "text-emerald-400"
      : tone === "negative"
        ? "text-rose-400"
        : tone === "warning"
          ? "text-amber-300"
          : "text-slate-100";

  return (
    <div className={`rounded-xl border p-4 transition-all hover:border-slate-700/80 ${toneBg}`}>
      <div className="flex items-center justify-between text-xs text-slate-400">
        <span className="font-medium tracking-wide">{label}</span>
        {icon && <span className="text-slate-500">{icon}</span>}
      </div>
      <div className={`mt-2 font-mono text-2xl font-bold tracking-tight ${valColor}`}>{value}</div>
      {subtext && <p className="mt-1 text-[11px] text-slate-400 leading-tight">{subtext}</p>}
    </div>
  );
}

export function SectionHeader({
  eyebrow,
  title,
  description,
  rightAction,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  rightAction?: React.ReactNode;
}) {
  return (
    <div className="mb-4 flex flex-wrap items-end justify-between gap-3 border-b border-slate-800/60 pb-3">
      <div>
        {eyebrow && (
          <p className="text-[10px] font-bold uppercase tracking-widest text-emerald-400 mb-0.5">
            {eyebrow}
          </p>
        )}
        <h2 className="text-lg md:text-xl font-bold text-slate-100 tracking-tight">{title}</h2>
        {description && <p className="mt-1 text-xs text-slate-400 max-w-2xl">{description}</p>}
      </div>
      {rightAction && <div>{rightAction}</div>}
    </div>
  );
}

export function EmptyState({
  title,
  message,
  action,
}: {
  title: string;
  message: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex min-h-[220px] flex-col items-center justify-center rounded-xl border border-dashed border-slate-800 bg-[#0D1421]/60 p-6 text-center">
      <h3 className="text-sm font-semibold text-slate-300">{title}</h3>
      <p className="mt-1 max-w-md text-xs text-slate-500">{message}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
