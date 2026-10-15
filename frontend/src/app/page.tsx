"use client";

import {
  useCallback,
  useEffect,
  useState,
} from "react";

import {
  Activity,
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  Building2,
  CheckCircle2,
  ChevronRight,
  Clock3,
  ExternalLink,
  FileText,
  Gauge,
  Layers3,
  LoaderCircle,
  Newspaper,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
  Target,
  TrendingUp,
  TriangleAlert,
  Wallet,
} from "lucide-react";


type AgentStatus =
  | "bullish"
  | "bearish"
  | "neutral"
  | "insufficient_data"
  | "unavailable"
  | string;

type AgentAssessment = {
  agent_name: string;
  status: AgentStatus;
  summary: string;
  evidence: string[];
  limitations: string[];
  source: string;
  is_demo: boolean;
};

type AgentDisagreement = {
  agents: string[];
  conflict: string;
  evidence: string[];
  significance: string;
};

type NewsArticle = {
  id?: string | null;
  title: string;
  publisher?: string | null;
  link?: string | null;
  published_at_utc: string;
  sentiment_score: number;
  sentiment_label: string;
  relevance_score: number;
  related_tickers: string[];
};

type IntelligenceResponse = {
  symbol: string;
  generated_at_utc: string;
  overall_status: AgentStatus;
  assessments: AgentAssessment[];
  disagreements: AgentDisagreement[];
  data_warnings: string[];
  analysis_note: string;
  news_sentiment_score: number | null;
  news_fetched_at_utc: string | null;
  news_articles: NewsArticle[];
};

type MarketQuote = {
  symbol?: string;
  price?: number | string | null;
  close?: number | string | null;
  latest_close?: number | string | null;
  current_price?: number | string | null;
  change?: number | string | null;
  change_percent?: number | string | null;
  open?: number | string | null;
  high?: number | string | null;
  low?: number | string | null;
  previous_close?: number | string | null;
  volume?: number | string | null;
  currency?: string | null;
  date?: string | null;
  source?: string | null;
  is_demo?: boolean;
  note?: string | null;
};


function numberValue(value: unknown): number | null {
  if (value === null || value === undefined || value === "") {
    return null;
  }

  const number = Number(value);

  return Number.isFinite(number) ? number : null;
}


function formatCurrency(
  value: number | null,
  currency = "USD",
): string {
  if (value === null) return "—";

  try {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency,
      maximumFractionDigits: 2,
    }).format(value);
  } catch {
    return `${currency} ${value.toLocaleString("en-US")}`;
  }
}




function formatSignedPercent(
  value: number | null,
): string {
  if (value === null) return "—";

  const prefix = value > 0 ? "+" : "";

  return `${prefix}${value.toFixed(2)}%`;
}


function formatDate(value?: string | null): string {
  if (!value) return "Timestamp unavailable";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}


function friendlyStatus(status: string): string {
  return status
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}


function statusClasses(status: string): string {
  switch (status) {
    case "bullish":
      return "border-emerald-400/20 bg-emerald-400/10 text-emerald-300";

    case "bearish":
      return "border-rose-400/20 bg-rose-400/10 text-rose-300";

    case "neutral":
      return "border-amber-400/20 bg-amber-400/10 text-amber-200";

    case "insufficient_data":
      return "border-orange-400/20 bg-orange-400/10 text-orange-200";

    case "unavailable":
      return "border-slate-500/30 bg-slate-500/10 text-slate-300";

    default:
      return "border-white/10 bg-white/5 text-slate-300";
  }
}


function sentimentClasses(label: string): string {
  if (label === "positive") {
    return "text-emerald-300 bg-emerald-400/10 border-emerald-400/20";
  }

  if (label === "negative") {
    return "text-rose-300 bg-rose-400/10 border-rose-400/20";
  }

  return "text-amber-200 bg-amber-400/10 border-amber-400/20";
}


function extractEvidenceValue(
  assessment: AgentAssessment | undefined,
  pattern: RegExp,
  suffix = "",
): string {
  for (const evidence of assessment?.evidence ?? []) {
    const match = evidence.match(pattern);

    if (match?.[1] !== undefined) {
      return `${match[1]}${suffix}`;
    }
  }

  return "—";
}


function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`inline-flex items-center gap-2 rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.11em] ${statusClasses(status)}`}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full ${
          status === "bullish"
            ? "bg-emerald-300"
            : status === "bearish"
              ? "bg-rose-300"
              : status === "neutral"
                ? "bg-amber-200"
                : "bg-slate-400"
        }`}
      />
      {friendlyStatus(status)}
    </span>
  );
}


function SectionHeading({
  eyebrow,
  title,
  description,
  right,
}: {
  eyebrow: string;
  title: string;
  description?: string;
  right?: React.ReactNode;
}) {
  return (
    <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div>
        <p className="eyebrow mb-1.5">{eyebrow}</p>
        <h2 className="text-xl font-semibold tracking-tight text-white md:text-2xl">
          {title}
        </h2>

        {description && (
          <p className="mt-1.5 max-w-2xl text-sm leading-6 text-slate-400">
            {description}
          </p>
        )}
      </div>

      {right}
    </div>
  );
}


function AgentIcon({ name }: { name: string }) {
  if (name.includes("Technical")) {
    return <Activity size={18} />;
  }

  if (name.includes("Fundamental")) {
    return <Building2 size={18} />;
  }

  return <Newspaper size={18} />;
}


function MetricCard({
  label,
  value,
  description,
  icon,
  tone = "default",
}: {
  label: string;
  value: string;
  description: string;
  icon: React.ReactNode;
  tone?: "default" | "positive" | "negative";
}) {
  const iconTone =
    tone === "positive"
      ? "text-emerald-300 bg-emerald-400/10"
      : tone === "negative"
        ? "text-rose-300 bg-rose-400/10"
        : "text-slate-300 bg-white/[0.06]";

  return (
    <div className="panel rounded-2xl p-4 transition duration-200 hover:border-white/[0.16] md:p-5">
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm text-slate-400">{label}</p>

        <span className={`rounded-xl p-2 ${iconTone}`}>
          {icon}
        </span>
      </div>

      <p className="mt-4 text-2xl font-semibold tracking-tight text-white md:text-[28px]">
        {value}
      </p>

      <p className="mt-2 text-xs leading-5 text-slate-500">
        {description}
      </p>
    </div>
  );
}


function AgentCard({
  assessment,
}: {
  assessment: AgentAssessment;
}) {
  const isDirectional =
    assessment.status === "bullish" ||
    assessment.status === "bearish";

  return (
    <article className="panel flex min-w-0 flex-col rounded-2xl p-5 transition duration-200 hover:border-white/[0.17]">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-white/[0.08] bg-white/[0.04] text-emerald-300">
            <AgentIcon name={assessment.agent_name} />
          </div>

          <div className="min-w-0">
            <h3 className="truncate text-sm font-semibold text-white">
              {assessment.agent_name}
            </h3>

            <p className="mt-1 truncate text-[11px] text-slate-500">
              {assessment.source}
            </p>
          </div>
        </div>
      </div>

      <div className="mt-4">
        <StatusBadge status={assessment.status} />
      </div>

      <p className="mt-4 min-h-[64px] text-sm leading-6 text-slate-300">
        {assessment.summary}
      </p>

      <div className="mt-4 border-t border-white/[0.07] pt-4">
        <p className="eyebrow mb-3">Supporting evidence</p>

        {assessment.evidence.length > 0 ? (
          <ul className="space-y-2.5">
            {assessment.evidence.slice(0, 4).map((item, index) => (
              <li
                key={`${assessment.agent_name}-${index}`}
                className="flex gap-2.5 text-xs leading-5 text-slate-400"
              >
                <span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-emerald-300/70" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-slate-500">
            No supporting evidence was returned.
          </p>
        )}
      </div>

      {assessment.limitations.length > 0 && (
        <details className="group mt-4 border-t border-white/[0.07] pt-3">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-3 text-xs font-medium text-slate-400 transition hover:text-white">
            <span className="flex items-center gap-2">
              <ShieldCheck size={14} />
              Limitations and caveats
            </span>

            <ChevronRight
              size={14}
              className="transition group-open:rotate-90"
            />
          </summary>

          <ul className="mt-3 space-y-2">
            {assessment.limitations.map((item, index) => (
              <li
                key={`${assessment.agent_name}-limitation-${index}`}
                className="text-xs leading-5 text-slate-500"
              >
                {item}
              </li>
            ))}
          </ul>
        </details>
      )}

      <div className="mt-auto flex items-center justify-between gap-2 pt-4">
        <span className="text-[10px] uppercase tracking-[0.12em] text-slate-600">
          {assessment.is_demo ? "Demo data" : "Provider data"}
        </span>

        {isDirectional ? (
          <span className="flex items-center gap-1.5 text-[11px] text-slate-400">
            {assessment.status === "bullish" ? (
              <TrendingUp size={13} className="text-emerald-300" />
            ) : (
              <ArrowDownRight size={13} className="text-rose-300" />
            )}
            Directional signal
          </span>
        ) : null}
      </div>
    </article>
  );
}


export default function Home() {
  const [tickerInput, setTickerInput] = useState("AAPL");
  const [activeSymbol, setActiveSymbol] = useState("AAPL");

  const [analysis, setAnalysis] =
    useState<IntelligenceResponse | null>(null);

  const [quote, setQuote] = useState<MarketQuote | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);

  const loadAnalysis = useCallback(async (rawSymbol: string) => {
    const symbol = rawSymbol.trim().toUpperCase();

    if (!/^[A-Z0-9.^=-]{1,24}$/.test(symbol)) {
      setError("Enter a valid ticker symbol, such as AAPL or MSFT.");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const encodedSymbol = encodeURIComponent(symbol);

      const [intelligenceResponse, quoteResponse] = await Promise.all([
        fetch(
          `/api/backend/api/v1/intelligence/analyze/${encodedSymbol}`,
          { cache: "no-store" },
        ),
        fetch(
          `/api/backend/api/v1/market/quote/${encodedSymbol}`,
          { cache: "no-store" },
        ).catch(() => null),
      ]);

      const intelligencePayload = await intelligenceResponse
        .json()
        .catch(() => null);

      if (!intelligenceResponse.ok) {
        const message =
          intelligencePayload?.detail ??
          `Intelligence request failed (${intelligenceResponse.status}).`;

        throw new Error(String(message));
      }

      let quotePayload: MarketQuote | null = null;

      if (quoteResponse?.ok) {
        quotePayload = await quoteResponse
          .json()
          .catch(() => null);
      }

      setAnalysis(intelligencePayload as IntelligenceResponse);
      setQuote(quotePayload);
      setActiveSymbol(symbol);
      setTickerInput(symbol);
      setUpdatedAt(new Date().toISOString());
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Unable to load market intelligence.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadAnalysis("AAPL");
    }, 0);

    return () => window.clearTimeout(timer);
  }, [loadAnalysis]);

  const assessments = analysis?.assessments ?? [];
  const technical = assessments.find(
    (item) => item.agent_name === "Technical Agent",
  );

  const fundamental = assessments.find(
    (item) => item.agent_name === "Fundamental Agent",
  );

  const sentiment = assessments.find(
    (item) => item.agent_name === "News Sentiment Agent",
  );

  const price = numberValue(
    quote?.price ??
      quote?.latest_close ??
      quote?.close ??
      quote?.current_price,
  );

  const dailyChangePercent = numberValue(quote?.change_percent);
  const currency = quote?.currency || "USD";

  const revenueGrowth = extractEvidenceValue(
    fundamental,
    /Revenue growth:\s*([+-]?\d+(?:\.\d+)?)%/i,
    "%",
  );

  const netMargin = extractEvidenceValue(
    fundamental,
    /Net profit margin:\s*([+-]?\d+(?:\.\d+)?)%/i,
    "%",
  );

  const roe = extractEvidenceValue(
    fundamental,
    /Return on equity:\s*([+-]?\d+(?:\.\d+)?)%/i,
    "%",
  );

  const peRatio = extractEvidenceValue(
    fundamental,
    /Trailing P\/E ratio:\s*([+-]?\d+(?:\.\d+)?)/i,
  );

  const currentRatio = extractEvidenceValue(
    fundamental,
    /Current ratio:\s*([+-]?\d+(?:\.\d+)?)/i,
  );

  const rsi = extractEvidenceValue(
    technical,
    /RSI\(14\) is\s*([+-]?\d+(?:\.\d+)?)/i,
  );

  const momentum = extractEvidenceValue(
    technical,
    /20-observation price momentum is\s*([+-]?\d+(?:\.\d+)?)%/i,
    "%",
  );

  const volatility = extractEvidenceValue(
    technical,
    /daily-return volatility is\s*([+-]?\d+(?:\.\d+)?)%/i,
    "%",
  );

  const articles = analysis?.news_articles ?? [];
  const warnings = analysis?.data_warnings ?? [];
  const disagreements = analysis?.disagreements ?? [];

  const directConflict = disagreements.length > 0;

  const bullishAgents = assessments.filter(
    (item) => item.status === "bullish" && !item.is_demo,
  );

  const bearishAgents = assessments.filter(
    (item) => item.status === "bearish" && !item.is_demo,
  );

  const sentimentScore = analysis?.news_sentiment_score ?? null;

  const sentimentScoreTone =
    sentimentScore === null
      ? "text-slate-400"
      : sentimentScore > 0
        ? "text-emerald-300"
        : sentimentScore < 0
          ? "text-rose-300"
          : "text-slate-300";

  return (
    <div className="terminal-grid min-h-screen text-slate-100">
      <div className="mx-auto grid min-h-screen max-w-[1900px] grid-cols-1 xl:grid-cols-[248px_minmax(0,1fr)]">

        <aside className="hidden flex-col border-r border-white/[0.07] bg-[#080c0b]/90 px-5 py-6 xl:flex">
          <a href="#overview" className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-emerald-300/25 bg-emerald-300/10 text-emerald-300">
              <Activity size={22} />
            </div>

            <div>
              <p className="text-lg font-semibold tracking-tight text-white">
                Vantage<span className="text-emerald-300">AI</span>
              </p>
              <p className="text-[10px] uppercase tracking-[0.2em] text-slate-500">
                Market intelligence
              </p>
            </div>
          </a>

          <div className="mt-10">
            <p className="eyebrow px-3">Workspace</p>

            <nav className="mt-3 space-y-1">
              <a href="#overview" className="nav-link nav-link-active">
                <Layers3 size={17} />
                Overview
                <ChevronRight size={15} className="ml-auto" />
              </a>

              <a href="#agents" className="nav-link">
                <Target size={17} />
                Agent insights
              </a>

              <a href="#disagreements" className="nav-link">
                <ShieldCheck size={17} />
                Disagreement intelligence
              </a>

              <a href="#news" className="nav-link">
                <Newspaper size={17} />
                News intelligence
              </a>

              <a href="#fundamentals" className="nav-link">
                <Wallet size={17} />
                Fundamentals
              </a>
            </nav>
          </div>

          <div className="mt-9">
            <p className="eyebrow px-3">Current coverage</p>

            <div className="mt-3 rounded-xl border border-white/[0.08] bg-white/[0.025] p-3.5">
              <div className="flex items-center justify-between">
                <span className="text-sm font-semibold text-white">
                  {activeSymbol}
                </span>
                <span className="h-2 w-2 rounded-full bg-emerald-300" />
              </div>

              <p className="mt-1 text-xs text-slate-500">
                Equity research
              </p>

              <div className="mt-4 flex items-center gap-2 text-[11px] text-slate-400">
                <Activity size={13} className="text-emerald-300" />
                3-agent analysis
              </div>
            </div>
          </div>

          <div className="mt-auto space-y-4 pt-10">
            <div className="rounded-xl border border-emerald-300/10 bg-emerald-300/[0.035] p-3.5">
              <div className="flex items-center gap-2 text-xs font-medium text-emerald-200">
                <ShieldCheck size={15} />
                Evidence-first research
              </div>

              <p className="mt-2 text-[11px] leading-5 text-slate-500">
                Inspect the evidence behind every signal. A status is not a
                prediction or a guarantee.
              </p>
            </div>

            <div className="flex items-center justify-between text-[10px] text-slate-600">
              <span>VANTAGEAI TERMINAL</span>
              <span>V1.0</span>
            </div>
          </div>
        </aside>

        <div className="min-w-0">
          <header className="sticky top-0 z-30 border-b border-white/[0.07] bg-[#080b0a]/90 backdrop-blur-xl">
            <div className="flex min-h-[76px] flex-wrap items-center justify-between gap-4 px-4 py-3 md:px-7">
              <div className="flex items-center gap-3 xl:hidden">
                <div className="flex h-9 w-9 items-center justify-center rounded-xl border border-emerald-300/25 bg-emerald-300/10 text-emerald-300">
                  <Activity size={20} />
                </div>

                <span className="font-semibold text-white">
                  Vantage<span className="text-emerald-300">AI</span>
                </span>
              </div>

              <div className="hidden min-w-0 xl:block">
                <div className="flex items-center gap-2 text-xs text-slate-500">
                  Intelligence workspace
                  <ChevronRight size={12} />
                  <span className="text-slate-300">{activeSymbol}</span>
                </div>

                <p className="mt-1 text-sm font-medium text-slate-300">
                  Evidence-backed market research
                </p>
              </div>

              <div className="ml-auto flex items-center gap-2.5 sm:gap-3">
                <form
                  onSubmit={(event) => {
                    event.preventDefault();
                    void loadAnalysis(tickerInput);
                  }}
                  className="flex h-10 w-[150px] items-center gap-2 rounded-xl border border-white/10 bg-white/[0.035] px-3 transition focus-within:border-emerald-300/40 sm:w-56"
                >
                  <Search size={16} className="shrink-0 text-slate-500" />

                  <input
                    aria-label="Search ticker symbol"
                    value={tickerInput}
                    onChange={(event) =>
                      setTickerInput(event.target.value.toUpperCase())
                    }
                    className="min-w-0 flex-1 bg-transparent text-sm font-medium text-white outline-none placeholder:text-slate-600"
                    placeholder="Ticker symbol"
                    maxLength={24}
                    autoCapitalize="characters"
                    spellCheck={false}
                  />

                  <button
                    type="submit"
                    title="Analyze ticker"
                    disabled={loading}
                    className="text-slate-500 transition hover:text-emerald-300 disabled:opacity-40"
                  >
                    <ArrowRight size={15} />
                  </button>
                </form>

                <button
                  onClick={() => void loadAnalysis(activeSymbol)}
                  disabled={loading}
                  title="Refresh analysis"
                  aria-label="Refresh analysis"
                  className="flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 bg-white/[0.035] text-slate-300 transition hover:border-emerald-300/30 hover:text-emerald-300 disabled:opacity-40"
                >
                  <RefreshCw
                    size={16}
                    className={loading ? "animate-spin" : ""}
                  />
                </button>
              </div>
            </div>
          </header>

          <main className="mx-auto max-w-[1550px] space-y-8 px-4 py-7 md:px-7 md:py-9">

            <section id="overview" className="scroll-mt-28">
              <div className="flex flex-col justify-between gap-5 lg:flex-row lg:items-end">
                <div>
                  <div className="mb-3 flex flex-wrap items-center gap-2">
                    <span className="inline-flex items-center gap-2 rounded-full border border-emerald-300/15 bg-emerald-300/[0.06] px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.15em] text-emerald-200">
                      <Sparkles size={13} />
                      Multi-agent intelligence
                    </span>

                    {analysis && (
                      <span className="inline-flex items-center gap-1.5 text-[11px] text-slate-500">
                        <CheckCircle2 size={13} className="text-emerald-300" />
                        API connected
                      </span>
                    )}
                  </div>

                  <h1 className="text-3xl font-semibold tracking-tight text-white md:text-[40px]">
                    One market.
                    <br className="sm:hidden" /> Three perspectives.
                  </h1>

                  <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-400 md:text-base">
                    Understand the evidence behind market movements,
                    company fundamentals, and news sentiment.
                  </p>
                </div>

                <div className="flex shrink-0 items-center gap-2 text-xs text-slate-500">
                  <Clock3 size={14} />
                  {updatedAt
                    ? `Updated ${formatDate(updatedAt)}`
                    : "Waiting for analysis"}
                </div>
              </div>

              {error && (
                <div className="mt-6 flex items-start gap-3 rounded-2xl border border-rose-400/20 bg-rose-400/[0.06] p-4">
                  <TriangleAlert
                    size={18}
                    className="mt-0.5 shrink-0 text-rose-300"
                  />

                  <div>
                    <p className="text-sm font-medium text-rose-200">
                      Unable to load the intelligence response
                    </p>
                    <p className="mt-1 text-sm leading-6 text-rose-100/70">
                      {error}
                    </p>
                  </div>
                </div>
              )}

              <div className="mt-6 grid grid-cols-1 gap-4 xl:grid-cols-[1.3fr_0.8fr]">
                <div className="panel relative overflow-hidden rounded-2xl p-5 md:p-7">
                  <div className="pointer-events-none absolute -right-14 -top-20 h-64 w-64 rounded-full bg-emerald-400/[0.07] blur-[80px]" />

                  <div className="relative flex flex-wrap items-start justify-between gap-4">
                    <div>
                      <div className="flex items-center gap-2">
                        <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-white/[0.08] bg-white/[0.04] text-emerald-300">
                          <BarChart3 size={19} />
                        </div>

                        <div>
                          <p className="text-sm font-medium text-white">
                            {activeSymbol}
                          </p>
                          <p className="mt-0.5 text-xs text-slate-500">
                            Market snapshot
                          </p>
                        </div>
                      </div>

                      <p className="mt-7 text-xs font-medium uppercase tracking-[0.17em] text-slate-500">
                        Latest available price
                      </p>

                      <div className="mt-2 flex flex-wrap items-baseline gap-3">
                        <h2 className="text-4xl font-semibold tracking-tight text-white md:text-5xl">
                          {formatCurrency(price, currency)}
                        </h2>

                        {dailyChangePercent !== null && (
                          <span
                            className={`inline-flex items-center gap-1 text-sm font-medium ${
                              dailyChangePercent >= 0
                                ? "text-emerald-300"
                                : "text-rose-300"
                            }`}
                          >
                            {dailyChangePercent >= 0 ? (
                              <ArrowUpRight size={16} />
                            ) : (
                              <ArrowDownRight size={16} />
                            )}
                            {formatSignedPercent(dailyChangePercent)}
                          </span>
                        )}
                      </div>

                      <p className="mt-3 text-xs leading-5 text-slate-500">
                        {quote?.date
                          ? `Provider date: ${quote.date}`
                          : "Price availability depends on the market data provider."}
                      </p>
                    </div>

                    <span
                      className={`rounded-full border px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.13em] ${
                        quote?.is_demo
                          ? "border-amber-300/20 bg-amber-300/10 text-amber-200"
                          : quote
                            ? "border-emerald-300/20 bg-emerald-300/10 text-emerald-200"
                            : "border-white/10 bg-white/[0.04] text-slate-400"
                      }`}
                    >
                      {quote?.is_demo
                        ? "Demo data"
                        : quote
                          ? "Provider data"
                          : "Quote unavailable"}
                    </span>
                  </div>

                  <div className="relative mt-7 grid grid-cols-2 gap-4 border-t border-white/[0.08] pt-5 sm:grid-cols-4">
                    {[
                      ["Open", numberValue(quote?.open)],
                      ["High", numberValue(quote?.high)],
                      ["Low", numberValue(quote?.low)],
                      ["Volume", numberValue(quote?.volume)],
                    ].map(([label, value]) => (
                      <div key={String(label)}>
                        <p className="text-xs text-slate-500">
                          {String(label)}
                        </p>

                        <p className="mt-2 text-sm font-semibold text-slate-200">
                          {label === "Volume"
                            ? value === null
                              ? "—"
                              : value.toLocaleString("en-US")
                            : formatCurrency(
                                value as number | null,
                                currency,
                              )}
                        </p>
                      </div>
                    ))}
                  </div>

                  <div className="relative mt-5 flex items-center gap-2 border-t border-white/[0.06] pt-4 text-[11px] text-slate-500">
                    <ShieldCheck size={13} className="text-emerald-300/80" />
                    Source: {quote?.source ?? "Quote source unavailable"}.
                    This is not necessarily a real-time exchange quote.
                  </div>
                </div>

                <div className="panel flex flex-col rounded-2xl p-5 md:p-7">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="eyebrow">Composite posture</p>
                      <h2 className="mt-2 text-xl font-semibold text-white">
                        Intelligence summary
                      </h2>
                    </div>

                    <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-white/[0.08] bg-white/[0.04] text-emerald-300">
                      <Gauge size={20} />
                    </div>
                  </div>

                  {analysis ? (
                    <>
                      <div className="mt-5">
                        <StatusBadge status={analysis.overall_status} />
                      </div>

                      <p className="mt-4 text-sm leading-6 text-slate-300">
                        {analysis.analysis_note}
                      </p>

                      <div className="mt-6 space-y-3 border-t border-white/[0.07] pt-4">
                        {assessments.map((assessment) => (
                          <div
                            key={assessment.agent_name}
                            className="flex items-center justify-between gap-3"
                          >
                            <span className="min-w-0 truncate text-xs text-slate-400">
                              {assessment.agent_name.replace(" Agent", "")}
                            </span>

                            <StatusBadge status={assessment.status} />
                          </div>
                        ))}
                      </div>
                    </>
                  ) : (
                    <div className="mt-6 flex flex-1 items-center justify-center py-8 text-sm text-slate-500">
                      {loading ? (
                        <span className="flex items-center gap-2">
                          <LoaderCircle
                            size={16}
                            className="animate-spin"
                          />
                          Loading intelligence...
                        </span>
                      ) : (
                        "No assessment available."
                      )}
                    </div>
                  )}
                </div>
              </div>

              <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <MetricCard
                  label="Revenue growth"
                  value={revenueGrowth}
                  description="Fundamental assessment"
                  icon={<TrendingUp size={17} />}
                  tone="positive"
                />

                <MetricCard
                  label="Net profit margin"
                  value={netMargin}
                  description="Fundamental assessment"
                  icon={<Wallet size={17} />}
                />

                <MetricCard
                  label="RSI · 14 periods"
                  value={rsi}
                  description="Historical momentum indicator"
                  icon={<Gauge size={17} />}
                />

                <MetricCard
                  label="News sentiment"
                  value={
                    sentimentScore === null
                      ? "—"
                      : `${sentimentScore > 0 ? "+" : ""}${sentimentScore.toFixed(3)}`
                  }
                  description={
                    sentiment
                      ? `Classification: ${friendlyStatus(sentiment.status)}`
                      : "News evidence unavailable"
                  }
                  icon={<Newspaper size={17} />}
                  tone={
                    sentimentScore !== null && sentimentScore > 0
                      ? "positive"
                      : sentimentScore !== null && sentimentScore < 0
                        ? "negative"
                        : "default"
                  }
                />
              </div>
            </section>

            <section id="agents" className="scroll-mt-28">
              <SectionHeading
                eyebrow="Independent perspectives"
                title="Agent intelligence"
                description="Each agent evaluates a different evidence source. Read the assessments separately before interpreting the combined view."
                right={
                  <span className="inline-flex items-center gap-2 rounded-lg border border-white/[0.08] bg-white/[0.025] px-3 py-2 text-xs text-slate-400">
                    <Layers3 size={14} />
                    {assessments.length} assessments
                  </span>
                }
              />

              {assessments.length > 0 ? (
                <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 2xl:grid-cols-3">
                  {assessments.map((assessment) => (
                    <AgentCard
                      key={assessment.agent_name}
                      assessment={assessment}
                    />
                  ))}
                </div>
              ) : (
                <div className="panel rounded-2xl p-8 text-center text-sm text-slate-500">
                  {loading
                    ? "Retrieving agent assessments..."
                    : "No agent assessments available."}
                </div>
              )}
            </section>

            <section id="fundamentals" className="scroll-mt-28">
              <SectionHeading
                eyebrow="Company quality and valuation"
                title="Fundamental snapshot"
                description="Metrics below are extracted from the Fundamental Agent's evidence. Their reporting periods may differ."
                right={
                  <span className="text-xs text-slate-500">
                    {fundamental?.source ?? "Awaiting fundamental data"}
                  </span>
                }
              />

              <div className="panel overflow-hidden rounded-2xl">
                <div className="grid grid-cols-1 divide-y divide-white/[0.07] sm:grid-cols-2 sm:divide-x sm:divide-y-0 xl:grid-cols-4">
                  {[
                    {
                      label: "Revenue growth",
                      value: revenueGrowth,
                      description: "Growth rate reported by the provider",
                      icon: <TrendingUp size={16} />,
                    },
                    {
                      label: "Net margin",
                      value: netMargin,
                      description: "Net income as a share of revenue",
                      icon: <Wallet size={16} />,
                    },
                    {
                      label: "Return on equity",
                      value: roe,
                      description: "Interpret high values with care",
                      icon: <Target size={16} />,
                    },
                    {
                      label: "Trailing P/E",
                      value: peRatio,
                      description: "Valuation relative to trailing earnings",
                      icon: <BarChart3 size={16} />,
                    },
                  ].map((metric) => (
                    <div key={metric.label} className="p-5 md:p-6">
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-xs text-slate-400">
                          {metric.label}
                        </p>
                        <span className="text-slate-500">
                          {metric.icon}
                        </span>
                      </div>

                      <p className="mt-4 text-2xl font-semibold text-white">
                        {metric.value}
                      </p>

                      <p className="mt-2 text-xs leading-5 text-slate-500">
                        {metric.description}
                      </p>
                    </div>
                  ))}
                </div>

                <div className="grid grid-cols-1 gap-0 border-t border-white/[0.07] md:grid-cols-3 md:divide-x md:divide-white/[0.07]">
                  <div className="flex items-center justify-between gap-3 border-b border-white/[0.07] px-5 py-4 md:border-b-0 md:px-6">
                    <div>
                      <p className="text-xs text-slate-400">
                        Current ratio
                      </p>
                      <p className="mt-1 text-sm text-slate-500">
                        Short-term liquidity
                      </p>
                    </div>
                    <p className="text-lg font-semibold text-white">
                      {currentRatio}
                    </p>
                  </div>

                  <div className="flex items-center justify-between gap-3 border-b border-white/[0.07] px-5 py-4 md:border-b-0 md:px-6">
                    <div>
                      <p className="text-xs text-slate-400">
                        20-period momentum
                      </p>
                      <p className="mt-1 text-sm text-slate-500">
                        Historical price change
                      </p>
                    </div>
                    <p className="text-lg font-semibold text-white">
                      {momentum}
                    </p>
                  </div>

                  <div className="flex items-center justify-between gap-3 px-5 py-4 md:px-6">
                    <div>
                      <p className="text-xs text-slate-400">
                        Daily volatility
                      </p>
                      <p className="mt-1 text-sm text-slate-500">
                        Recent return variability
                      </p>
                    </div>
                    <p className="text-lg font-semibold text-white">
                      {volatility}
                    </p>
                  </div>
                </div>
              </div>

              <p className="mt-3 text-xs leading-5 text-slate-600">
                Fundamental thresholds are prototype heuristics, not a
                validated investment strategy. Some metrics can describe
                different financial reporting periods.
              </p>
            </section>

            <section id="disagreements" className="scroll-mt-28">
              <SectionHeading
                eyebrow="Cross-agent interpretation"
                title="Disagreement intelligence"
                description="Separate direct bullish-versus-bearish conflicts from situations where one agent is directional and another is neutral."
              />

              <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1.2fr_0.8fr]">
                <div className="panel rounded-2xl p-5 md:p-6">
                  <div className="flex items-start gap-3">
                    <div
                      className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${
                        directConflict
                          ? "bg-rose-400/10 text-rose-300"
                          : "bg-emerald-400/10 text-emerald-300"
                      }`}
                    >
                      {directConflict ? (
                        <TriangleAlert size={19} />
                      ) : (
                        <ShieldCheck size={19} />
                      )}
                    </div>

                    <div className="min-w-0">
                      <h3 className="text-base font-semibold text-white">
                        {directConflict
                          ? "Opposing directional signals detected"
                          : "No direct directional conflict detected"}
                      </h3>

                      <p className="mt-1.5 text-sm leading-6 text-slate-400">
                        {analysis?.analysis_note ??
                          "Agent analysis is not available yet."}
                      </p>
                    </div>
                  </div>

                  {disagreements.length > 0 ? (
                    <div className="mt-6 space-y-3">
                      {disagreements.map((item, index) => (
                        <div
                          key={`${item.conflict}-${index}`}
                          className="rounded-xl border border-rose-400/15 bg-rose-400/[0.04] p-4"
                        >
                          <div className="flex flex-wrap items-center gap-2">
                            {item.agents.map((agent) => (
                              <span
                                key={agent}
                                className="rounded-md border border-white/[0.08] bg-white/[0.04] px-2 py-1 text-xs text-slate-300"
                              >
                                {agent}
                              </span>
                            ))}

                            <span className="rounded-md bg-rose-400/10 px-2 py-1 text-[10px] uppercase tracking-wider text-rose-200">
                              {item.significance} significance
                            </span>
                          </div>

                          <p className="mt-3 text-sm leading-6 text-slate-200">
                            {item.conflict}
                          </p>

                          {item.evidence.map((text, evidenceIndex) => (
                            <p
                              key={`${text}-${evidenceIndex}`}
                              className="mt-2 text-xs leading-5 text-slate-400"
                            >
                              {text}
                            </p>
                          ))}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="mt-6 rounded-xl border border-white/[0.07] bg-white/[0.02] p-4">
                      <p className="text-xs font-medium uppercase tracking-[0.13em] text-slate-400">
                        Current signal distribution
                      </p>

                      <div className="mt-4 space-y-3">
                        {assessments.map((item) => (
                          <div
                            key={item.agent_name}
                            className="flex flex-wrap items-center justify-between gap-3"
                          >
                            <span className="text-sm text-slate-300">
                              {item.agent_name}
                            </span>
                            <StatusBadge status={item.status} />
                          </div>
                        ))}
                      </div>

                      <p className="mt-4 border-t border-white/[0.07] pt-3 text-xs leading-5 text-slate-500">
                        Neutral does not mean bearish. It means the
                        configured rules did not establish a directional
                        signal for that agent.
                      </p>
                    </div>
                  )}
                </div>

                <div className="panel rounded-2xl p-5 md:p-6">
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-300/10 text-amber-200">
                      <TriangleAlert size={18} />
                    </div>

                    <div>
                      <h3 className="text-base font-semibold text-white">
                        Evidence to keep in mind
                      </h3>
                      <p className="mt-1 text-xs text-slate-500">
                        Data quality and model caveats
                      </p>
                    </div>
                  </div>

                  <div className="mt-5 space-y-3">
                    {warnings.length > 0 ? (
                      warnings.slice(0, 6).map((warning, index) => (
                        <div
                          key={`${warning}-${index}`}
                          className="flex gap-2.5 text-xs leading-5 text-slate-400"
                        >
                          <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-amber-200/80" />
                          <span>{warning}</span>
                        </div>
                      ))
                    ) : (
                      <p className="text-sm text-slate-500">
                        No warnings were returned by the API.
                      </p>
                    )}
                  </div>

                  {bullishAgents.length > 0 && bearishAgents.length === 0 && (
                    <div className="mt-5 rounded-xl border border-emerald-400/10 bg-emerald-400/[0.035] p-3.5">
                      <div className="flex items-center gap-2 text-xs font-medium text-emerald-200">
                        <CheckCircle2 size={14} />
                        Directional support is partial
                      </div>
                      <p className="mt-2 text-xs leading-5 text-slate-400">
                        {bullishAgents.length} agent
                        {bullishAgents.length === 1 ? "" : "s"} currently
                        indicate bullish conditions. Other agents may be
                        neutral or unable to establish direction.
                      </p>
                    </div>
                  )}
                </div>
              </div>
            </section>

            <section id="news" className="scroll-mt-28">
              <SectionHeading
                eyebrow="News and market context"
                title="News intelligence"
                description="Review the original headlines and their rule-based sentiment labels. Scores reflect headline wording, not expected stock returns."
                right={
                  <span className="rounded-lg border border-white/[0.08] bg-white/[0.025] px-3 py-2 text-xs text-slate-400">
                    {articles.length} articles
                  </span>
                }
              />

              <div className="panel overflow-hidden rounded-2xl">
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/[0.07] px-5 py-4 md:px-6">
                  <div className="flex items-center gap-2.5">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-white/[0.045] text-emerald-300">
                      <Newspaper size={17} />
                    </div>

                    <div>
                      <p className="text-sm font-medium text-white">
                        Headlines for {activeSymbol}
                      </p>
                      <p className="mt-0.5 text-[11px] text-slate-500">
                        Sorted by provider publication timestamp
                      </p>
                    </div>
                  </div>

                  <div className={`text-sm font-semibold ${sentimentScoreTone}`}>
                    {sentimentScore === null
                      ? "Score unavailable"
                      : `Aggregate ${sentimentScore > 0 ? "+" : ""}${sentimentScore.toFixed(3)}`}
                  </div>
                </div>

                {articles.length > 0 ? (
                  <div className="divide-y divide-white/[0.06]">
                    {articles.map((article, index) => (
                      <article
                        key={
                          article.id ??
                          `${article.title}-${article.published_at_utc}-${index}`
                        }
                        className="group flex flex-col gap-4 px-5 py-5 transition hover:bg-white/[0.018] md:flex-row md:items-start md:px-6"
                      >
                        <div className="hidden h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-white/[0.07] bg-white/[0.025] text-slate-500 md:flex">
                          <FileText size={16} />
                        </div>

                        <div className="min-w-0 flex-1">
                          <div className="mb-2 flex flex-wrap items-center gap-2">
                            <span
                              className={`rounded-md border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.1em] ${sentimentClasses(article.sentiment_label)}`}
                            >
                              {article.sentiment_label}
                            </span>

                            <span className="text-[11px] text-slate-500">
                              Score {article.sentiment_score > 0 ? "+" : ""}
                              {article.sentiment_score.toFixed(2)}
                            </span>

                            <span className="text-[11px] text-slate-600">
                              ·
                            </span>

                            <span className="text-[11px] text-slate-500">
                              {article.publisher || "Publisher unavailable"}
                            </span>
                          </div>

                          <h3 className="max-w-4xl text-sm font-medium leading-6 text-slate-200 transition group-hover:text-white">
                            {article.title}
                          </h3>

                          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-2 text-[11px] text-slate-500">
                            <span className="inline-flex items-center gap-1.5">
                              <Clock3 size={12} />
                              {formatDate(article.published_at_utc)}
                            </span>

                            <span>
                              Relevance{" "}
                              {Math.round(article.relevance_score * 100)}%
                            </span>
                          </div>
                        </div>

                        {article.link && (
                          <a
                            href={article.link}
                            target="_blank"
                            rel="noreferrer"
                            aria-label={`Open article: ${article.title}`}
                            className="inline-flex shrink-0 items-center gap-1.5 self-start rounded-lg border border-white/[0.08] px-3 py-2 text-xs text-slate-400 transition hover:border-emerald-300/25 hover:text-emerald-200 md:mt-1"
                          >
                            Read source
                            <ExternalLink size={13} />
                          </a>
                        )}
                      </article>
                    ))}
                  </div>
                ) : (
                  <div className="p-8 text-center">
                    <Newspaper
                      size={24}
                      className="mx-auto text-slate-600"
                    />
                    <p className="mt-3 text-sm text-slate-400">
                      {loading
                        ? "Fetching recent headlines..."
                        : "No usable news articles were returned."}
                    </p>
                  </div>
                )}

                <div className="border-t border-white/[0.07] px-5 py-4 md:px-6">
                  <p className="text-[11px] leading-5 text-slate-500">
                    Source: Yahoo Finance through yfinance. Headlines are
                    classified using a prototype keyword-based heuristic.
                    Review the article itself before drawing a conclusion.
                  </p>
                </div>
              </div>
            </section>

            <footer className="border-t border-white/[0.07] pb-4 pt-6">
              <div className="flex flex-col justify-between gap-3 text-xs leading-5 text-slate-500 md:flex-row md:items-center">
                <div className="flex items-center gap-2">
                  <ShieldCheck size={14} className="text-emerald-300/80" />
                  Evidence-backed analysis. No automated trade execution.
                </div>

                <p>
                  Informational research only · Not personalized investment advice
                </p>
              </div>
            </footer>

          </main>
        </div>
      </div>
    </div>
  );
}
