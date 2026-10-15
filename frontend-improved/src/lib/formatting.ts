export function numberValue(value: unknown): number | null {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  const num = Number(value);
  return Number.isFinite(num) ? num : null;
}

export function formatCurrency(
  value: number | null | undefined,
  currency = "USD",
): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";

  try {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency,
      maximumFractionDigits: 2,
    }).format(value);
  } catch {
    return `${currency} ${value.toLocaleString("en-US", { maximumFractionDigits: 2 })}`;
  }
}

export function formatCompactNumber(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";

  return new Intl.NumberFormat("en-US", {
    notation: "compact",
    compactDisplay: "short",
    maximumFractionDigits: 2,
  }).format(value);
}

export function formatSignedPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";

  const prefix = value > 0 ? "+" : "";
  return `${prefix}${value.toFixed(2)}%`;
}

export function formatDate(value?: string | null): string {
  if (!value) return "Timestamp unavailable";

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZoneName: "short",
  }).format(date);
}

export function formatTradingDay(value?: string | null): string {
  if (!value) return "—";
  return value;
}

export function friendlyStatus(status: string): string {
  if (!status) return "Unavailable";
  return status
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function statusClasses(status: string): string {
  switch (status?.toLowerCase()) {
    case "bullish":
      return "border-emerald-500/30 bg-emerald-500/10 text-emerald-400";
    case "bearish":
      return "border-rose-500/30 bg-rose-500/10 text-rose-400";
    case "neutral":
      return "border-amber-500/30 bg-amber-500/10 text-amber-300";
    case "insufficient_data":
      return "border-orange-500/30 bg-orange-500/10 text-orange-300";
    case "unavailable":
      return "border-slate-600/40 bg-slate-800/40 text-slate-400";
    default:
      return "border-slate-700 bg-slate-800/50 text-slate-300";
  }
}

export function sentimentClasses(label: string): string {
  switch (label?.toLowerCase()) {
    case "positive":
      return "text-emerald-400 bg-emerald-500/10 border-emerald-500/30";
    case "negative":
      return "text-rose-400 bg-rose-500/10 border-rose-500/30";
    default:
      return "text-amber-300 bg-amber-500/10 border-amber-500/30";
  }
}
