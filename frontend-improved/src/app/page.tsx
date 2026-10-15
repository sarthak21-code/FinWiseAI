"use client";

import React from "react";
import { useStockData } from "@/lib/stock-context";
import { PriceHistoryChart } from "@/components/charts/PriceHistoryChart";
import { AgentComparison } from "@/components/charts/AgentComparison";
import { StatusBadge, MetricCard, SectionHeader } from "@/components/shared/CommonComponents";
import {
  formatCurrency,
  formatSignedPercent,
  formatCompactNumber,
  formatTradingDay,
  numberValue,
} from "@/lib/formatting";
import {
  TrendingUp,
  TrendingDown,
  ArrowRight,
  ExternalLink,
  AlertTriangle,
} from "lucide-react";

export default function OverviewPage() {
  const { symbol, quote, history, technical, fundamental, intelligence } =
    useStockData();
  const queryStr = `?ticker=${encodeURIComponent(symbol)}`;

  const latestPrice = numberValue(quote?.price ?? quote?.latest_close ?? history?.bars?.slice(-1)[0]?.close ?? null);
  const changeVal = numberValue(quote?.change ?? null);
  const changePct = numberValue(quote?.change_percent ?? null);
  const currency = quote?.currency || fundamental?.currency || "USD";
  const tradingDay = quote?.latest_trading_day || history?.bars?.slice(-1)[0]?.trading_day;
  const companyName = fundamental?.company_name || null;
  const isPositive = (changeVal ?? 0) >= 0;

  // Key Insights derived from real backend evidence
  const insights: { title: string; text: string; tone: "positive" | "negative" | "warning" | "neutral" }[] = [];

  const sma20Val = numberValue(technical?.sma_20 ?? null);
  if (sma20Val !== null && latestPrice !== null) {
    const diff20 = ((latestPrice / sma20Val) - 1) * 100;
    if (diff20 > 0) {
      insights.push({
        title: "Trading Above 20-Day SMA",
        text: `Latest close is ${Math.abs(diff20).toFixed(2)}% above the 20-observation moving average (${formatCurrency(sma20Val, currency)}).`,
        tone: "positive",
      });
    } else {
      insights.push({
        title: "Trading Below 20-Day SMA",
        text: `Latest close is ${Math.abs(diff20).toFixed(2)}% below the 20-observation moving average (${formatCurrency(sma20Val, currency)}).`,
        tone: "negative",
      });
    }
  }

  if (intelligence?.disagreements && intelligence.disagreements.length > 0) {
    insights.push({
      title: "Agent Disagreement Detected",
      text: `${intelligence.disagreements[0].agents.join(" and ")} hold conflicting directional views. The overall rating is governed by multi-agent checks.`,
      tone: "warning",
    });
  }

  if (fundamental?.pe_ratio) {
    const reportedPeriod = [fundamental.fiscal_period, fundamental.fiscal_year]
      .filter(Boolean)
      .join(" ");
    insights.push({
      title: "Valuation Benchmark",
      text: reportedPeriod
        ? `Trailing P/E ratio is ${fundamental.pe_ratio.toFixed(2)}x (provider period: ${reportedPeriod}).`
        : `Trailing P/E ratio is ${fundamental.pe_ratio.toFixed(2)}x; the provider did not supply a fiscal period.`,
      tone: "neutral",
    });
  }

  const recentNews = intelligence?.news_articles?.slice(0, 4) || [];

  return (
    <div className="space-y-6">
      {/* SECTION A: Stock Identity & First Viewport Header */}
      <div className="flex flex-wrap items-start justify-between gap-4 rounded-xl border border-slate-800/80 bg-[#0D1421] p-5 shadow-sm">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="font-mono text-3xl font-extrabold tracking-tight text-slate-100">
              {symbol}
            </h1>
            {companyName && (
              <span className="text-base font-medium text-slate-400">
                {companyName}
              </span>
            )}
            {quote?.is_demo && (
              <span className="rounded bg-amber-500/10 px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider text-amber-400 border border-amber-500/20">
                Demo Snapshot
              </span>
            )}
          </div>

          <div className="mt-2 flex flex-wrap items-center gap-4 text-xs text-slate-400">
            <span>Trading Date: <strong className="font-mono text-slate-300">{formatTradingDay(tradingDay)}</strong></span>
            <span>•</span>
            <span>Source: <span className="font-mono text-slate-300">{quote?.source || history?.source || "Provider Data"}</span></span>
            <span>•</span>
            <span className="text-slate-500">Market data delayed / EOD close</span>
          </div>
        </div>

        {/* Current Price & Daily Delta */}
        <div className="text-right">
          <div className="font-mono text-3xl font-bold tracking-tight text-slate-100">
            {formatCurrency(latestPrice, currency)}
          </div>
          <div className="mt-1 flex items-center justify-end gap-1.5 font-mono text-sm font-semibold">
            {changeVal !== null ? (
              <span className={isPositive ? "text-emerald-400" : "text-rose-400"}>
                {isPositive ? "+" : ""}{changeVal.toFixed(2)} ({formatSignedPercent(changePct)})
              </span>
            ) : (
              <span className="text-slate-500">Daily delta unavailable</span>
            )}
            {changeVal !== null && (
              isPositive ? <TrendingUp size={16} className="text-emerald-400" /> : <TrendingDown size={16} className="text-rose-400" />
            )}
          </div>
        </div>
      </div>

      {/* Personalized Investor Mandate Context */}
      {intelligence?.personalized_interpretation && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-800 bg-[#111B2B] px-4 py-3 text-xs">
          <div className="flex items-center gap-2.5">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-emerald-500/10 text-emerald-400 font-bold">
              ✓
            </span>
            <div>
              <span className="font-semibold text-slate-200">
                Personalized for {intelligence.personalized_interpretation.profile_name} (Risk: {intelligence.personalized_interpretation.risk_tolerance}/5):
              </span>
              <span className="ml-2 text-slate-300">
                Suitability: <strong className="text-emerald-400">{intelligence.personalized_interpretation.suitability_rating}</strong>
              </span>
            </div>
          </div>
          <a
            href={`/portfolio${queryStr}`}
            className="flex items-center gap-1 font-semibold text-emerald-400 hover:underline"
          >
            <span>Examine Portfolio Risk</span>
            <ArrowRight size={12} />
          </a>
        </div>
      )}

      {/* SECTION B: Market KPI Cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <MetricCard
          label="Latest Close"
          value={formatCurrency(latestPrice, currency)}
          subtext={`As of ${tradingDay || "latest"}`}
        />
        <MetricCard
          label="Day Change"
          value={formatSignedPercent(changePct)}
          tone={changePct !== null ? (changePct >= 0 ? "positive" : "negative") : "neutral"}
          subtext={changeVal !== null ? `${changeVal > 0 ? "+" : ""}${changeVal.toFixed(2)} ${currency}` : undefined}
        />
        <MetricCard
          label="Trading Volume"
          value={formatCompactNumber(numberValue(quote?.volume ?? history?.bars?.slice(-1)[0]?.volume))}
          subtext="Shares reported"
        />
        <MetricCard
          label="Day High"
          value={formatCurrency(numberValue(quote?.high ?? history?.bars?.slice(-1)[0]?.high), currency)}
          subtext="Session peak"
        />
        <MetricCard
          label="Day Low"
          value={formatCurrency(numberValue(quote?.low ?? history?.bars?.slice(-1)[0]?.low), currency)}
          subtext="Session trough"
        />
        <MetricCard
          label="SMA 20 Dist."
          value={
            sma20Val !== null && latestPrice !== null
              ? formatSignedPercent(((latestPrice / sma20Val) - 1) * 100)
              : "—"
          }
          tone={
            sma20Val !== null && latestPrice !== null
              ? latestPrice >= sma20Val ? "positive" : "negative"
              : "neutral"
          }
          subtext="vs 20-day trend"
        />
      </div>

      {/* SECTION C & D: Primary Price Chart & Overall Assessment */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Price History Chart (2 Cols on lg) */}
        <div className="lg:col-span-2">
          <PriceHistoryChart
            bars={history?.bars || []}
            currency={currency}
            sourceNote={history?.source}
          />
        </div>

        {/* Intelligence Summary Panel (1 Col on lg) */}
        <div className="flex flex-col justify-between rounded-xl border border-slate-800/80 bg-[#0D1421] p-5">
          <div>
            <div className="flex items-center justify-between border-b border-slate-800/60 pb-3">
              <div>
                <p className="text-[10px] font-bold uppercase tracking-widest text-emerald-400">
                  Synthesized Verdict
                </p>
                <h3 className="text-base font-bold text-slate-100">
                  Overall Intelligence Status
                </h3>
              </div>
              <StatusBadge status={intelligence?.overall_status || "insufficient_data"} />
            </div>

            <p className="mt-4 text-xs leading-relaxed text-slate-300">
              {intelligence?.analysis_note || "FinWiseAI evaluates technical trend, fundamental metrics, and news sentiment independently."}
            </p>

            {/* Metrics breakdown */}
            <div className="mt-4 space-y-2 rounded-lg border border-slate-800/80 bg-slate-950/60 p-3 text-xs">
              <div className="flex justify-between text-slate-400">
                <span>Active Analytical Agents:</span>
                <span className="font-mono font-bold text-slate-200">
                  {intelligence?.assessments?.length || 0}
                </span>
              </div>
              <div className="flex justify-between text-slate-400">
                <span>Direct Conflicts:</span>
                <span className="font-mono font-bold text-amber-400">
                  {intelligence?.disagreements?.length || 0}
                </span>
              </div>
              <div className="flex justify-between text-slate-400">
                <span>News Sentiment Score:</span>
                <span className="font-mono font-bold text-slate-200">
                  {intelligence?.news_sentiment_score !== null && intelligence?.news_sentiment_score !== undefined
                    ? intelligence.news_sentiment_score.toFixed(2)
                    : "N/A"}
                </span>
              </div>
            </div>

            {/* Data Warnings */}
            {intelligence?.data_warnings && intelligence.data_warnings.length > 0 && (
              <div className="mt-4 space-y-1.5">
                <p className="text-[10px] font-bold uppercase tracking-wider text-amber-400 flex items-center gap-1">
                  <AlertTriangle size={12} />
                  <span>Evidence Caveats</span>
                </p>
                <div className="rounded border border-amber-500/20 bg-amber-500/5 p-2 text-[11px] text-amber-200/90 leading-tight">
                  {intelligence.data_warnings[0]}
                </div>
              </div>
            )}
          </div>

          <div className="mt-6 border-t border-slate-800/60 pt-3">
            <a
              href={`/intelligence${queryStr}`}
              className="flex items-center justify-between text-xs font-semibold text-emerald-400 hover:text-emerald-300 transition"
            >
              <span>Examine Agent Disagreement Intelligence</span>
              <ArrowRight size={14} />
            </a>
          </div>
        </div>
      </div>

      {/* SECTION E: Agent Comparison Overview */}
      <div>
        <SectionHeader
          eyebrow="Multi-Perspective Analysis"
          title="Analytical Agent Perspectives"
          description="Independent specialized assessments. FinWiseAI displays genuine disagreement rather than concealing conflicting views."
          rightAction={
            <a
              href={`/intelligence${queryStr}`}
              className="flex items-center gap-1 text-xs font-semibold text-emerald-400 hover:text-emerald-300"
            >
              <span>View Full Intelligence Trace</span>
              <ArrowRight size={13} />
            </a>
          }
        />
        <AgentComparison assessments={intelligence?.assessments || []} />
      </div>

      {/* SECTION F & G: Key Insights & Recent News Preview */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Key Insights Panel */}
        <div className="rounded-xl border border-slate-800/80 bg-[#0D1421] p-5">
          <h3 className="text-sm font-bold tracking-tight text-slate-200 mb-3">
            Evidence-Derived Key Insights
          </h3>
          {insights.length > 0 ? (
            <div className="space-y-3">
              {insights.map((ins, idx) => (
                <div
                  key={idx}
                  className="rounded-lg border border-slate-800/80 bg-slate-900/50 p-3"
                >
                  <h4 className="text-xs font-bold text-slate-200 flex items-center gap-2">
                    <span
                      className={`h-1.5 w-1.5 rounded-full ${
                        ins.tone === "positive"
                          ? "bg-emerald-400"
                          : ins.tone === "negative"
                            ? "bg-rose-400"
                            : ins.tone === "warning"
                              ? "bg-amber-400"
                              : "bg-blue-400"
                      }`}
                    />
                    {ins.title}
                  </h4>
                  <p className="mt-1 text-xs text-slate-400 leading-relaxed">
                    {ins.text}
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-slate-500 italic">
              No evidence-backed insights could be derived from the available data.
            </p>
          )}
        </div>

        {/* Recent News Preview */}
        <div className="rounded-xl border border-slate-800/80 bg-[#0D1421] p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-bold tracking-tight text-slate-200">
              Recent News Intelligence Preview
            </h3>
            <a
              href={`/news${queryStr}`}
              className="text-xs font-semibold text-emerald-400 hover:text-emerald-300 flex items-center gap-1"
            >
              <span>All News</span>
              <ArrowRight size={13} />
            </a>
          </div>

          {recentNews.length > 0 ? (
            <div className="space-y-2.5">
              {recentNews.map((article, idx) => (
                <div
                  key={idx}
                  className="rounded-lg border border-slate-800/60 bg-slate-900/40 p-2.5 text-xs transition hover:border-slate-700/80"
                >
                  <div className="flex items-start justify-between gap-2">
                    <p className="font-medium text-slate-200 line-clamp-2 leading-snug">
                      {article.title}
                    </p>
                    {article.link && (
                      <a
                        href={article.link}
                        target="_blank"
                        rel="noreferrer noopener"
                        className="text-slate-500 hover:text-slate-300 shrink-0"
                      >
                        <ExternalLink size={13} />
                      </a>
                    )}
                  </div>
                  <div className="mt-2 flex items-center justify-between text-[10px] text-slate-500 font-mono">
                    <span>{article.publisher || "Financial Wire"}</span>
                    <span
                      className={`font-semibold uppercase tracking-wider ${
                        article.sentiment_label === "positive"
                          ? "text-emerald-400"
                          : article.sentiment_label === "negative"
                            ? "text-rose-400"
                            : "text-amber-300"
                      }`}
                    >
                      {article.sentiment_label} ({article.sentiment_score.toFixed(2)})
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-slate-500 italic">
              No recent news headlines available for this symbol.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
