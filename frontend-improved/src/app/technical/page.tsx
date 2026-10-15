"use client";

import React from "react";
import { useStockData } from "@/lib/stock-context";
import { SectionHeader, MetricCard, StatusBadge } from "@/components/shared/CommonComponents";
import { PriceMovingAverageChart } from "@/components/charts/PriceMovingAverageChart";
import { RsiChart } from "@/components/charts/RsiChart";
import { DailyReturnsChart } from "@/components/charts/DailyReturnsChart";
import { VolumeChart } from "@/components/charts/VolumeChart";
import { formatCurrency, formatSignedPercent, formatTradingDay, numberValue } from "@/lib/formatting";
import { ShieldCheck, Activity } from "lucide-react";

export default function TechnicalPage() {
  const { symbol, quote, history, technical } = useStockData();
  const bars = history?.bars || [];
  const currency = quote?.currency || "USD";

  const latestClose = numberValue(technical?.latest_close ?? quote?.price ?? quote?.latest_close ?? null);
  const sma20 = numberValue(technical?.sma_20 ?? null);
  const sma50 = numberValue(technical?.sma_50 ?? null);
  const rsi = numberValue(technical?.rsi_14 ?? null);
  const momentum = numberValue(technical?.momentum_20d_percent ?? null);
  const volatility = numberValue(technical?.daily_volatility_percent ?? null);

  const cleanEvidence = (technical?.evidence || []).filter((e) => e && e.trim().length > 0);

  return (
    <div className="space-y-6">
      <SectionHeader
        eyebrow="Quantitative Engine"
        title={`Technical Analysis — ${symbol}`}
        description="Rule-based indicators calculated from available provider-reported daily price observations."
        rightAction={<StatusBadge status={technical?.technical_bias || "insufficient_data"} />}
      />

      {/* SECTION A: Technical Summary KPI Cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <MetricCard
          label="Latest Close"
          value={formatCurrency(latestClose, currency)}
          subtext={`Trading day: ${formatTradingDay(technical?.latest_trading_day)}`}
        />
        <MetricCard
          label="SMA 20"
          value={formatCurrency(sma20, currency)}
          tone={latestClose !== null && sma20 !== null ? (latestClose >= sma20 ? "positive" : "negative") : "neutral"}
          subtext={latestClose !== null && sma20 !== null ? `${latestClose >= sma20 ? "Above" : "Below"} 20-day mean` : "Insufficient history"}
        />
        <MetricCard
          label="SMA 50"
          value={formatCurrency(sma50, currency)}
          tone={latestClose !== null && sma50 !== null ? (latestClose >= sma50 ? "positive" : "negative") : "neutral"}
          subtext={latestClose !== null && sma50 !== null ? `${latestClose >= sma50 ? "Above" : "Below"} 50-day mean` : "Insufficient history"}
        />
        <MetricCard
          label="RSI (14)"
          value={rsi !== null ? rsi.toFixed(2) : "—"}
          tone={rsi !== null ? (rsi >= 55 ? "positive" : rsi <= 45 ? "negative" : "warning") : "neutral"}
          subtext="14-day relative strength"
        />
        <MetricCard
          label="20D Momentum"
          value={momentum !== null ? formatSignedPercent(momentum) : "—"}
          tone={momentum !== null ? (momentum >= 0 ? "positive" : "negative") : "neutral"}
          subtext="20-observation velocity"
        />
        <MetricCard
          label="Daily Volatility"
          value={volatility !== null ? `${volatility.toFixed(2)}%` : "—"}
          subtext="Recent 20D std deviation"
        />
      </div>

      {/* SECTION B: Main Moving Averages Price Chart */}
      <PriceMovingAverageChart bars={bars} currency={currency} />

      {/* SECTION C & D: RSI Chart & Daily Returns Chart */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <RsiChart bars={bars} currentRsi={rsi} />
        <DailyReturnsChart bars={bars} />
      </div>

      {/* SECTION G: Volume Chart */}
      <VolumeChart bars={bars} />

      {/* SECTION H & I: Technical Interpretation & Limitations */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Interpretation & Rule-based classification */}
        <div className="rounded-xl border border-slate-800/80 bg-[#0D1421] p-5">
          <div className="flex items-center gap-2 text-slate-200 mb-3 font-semibold text-sm">
            <Activity size={16} className="text-emerald-400" />
            <span>Rule-Based Analytical Interpretation</span>
          </div>

          {cleanEvidence.length > 0 ? (
            <ul className="space-y-2">
              {cleanEvidence.map((ev, idx) => (
                <li key={idx} className="flex items-start gap-2 text-xs text-slate-300 leading-relaxed">
                  <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-400" />
                  <span>{ev}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-slate-500 italic">
              No technical signals could be evaluated due to insufficient data.
            </p>
          )}

          <div className="mt-4 rounded-lg border border-slate-800/80 bg-slate-900/60 p-3 text-[11px] text-slate-400">
            <strong>Engine Rule:</strong> Bullish requires Close &gt; SMA20, RSI &ge; 55, and 20D Momentum &gt; 0%. Bearish requires Close &lt; SMA20, RSI &le; 45, and 20D Momentum &lt; 0%. If opposing or intermediate, status is Neutral.
          </div>
        </div>

        {/* Technical Limitations */}
        <div className="rounded-xl border border-slate-800/80 bg-[#0D1421] p-5">
          <div className="flex items-center gap-2 text-amber-400 mb-3 font-semibold text-sm">
            <ShieldCheck size={16} />
            <span>Quantitative Limitations & Data Integrity</span>
          </div>

          <div className="space-y-2.5 text-xs text-slate-400 leading-relaxed">
            <p>
              • <strong>Provider Source:</strong> {technical?.source || history?.source || "Configured data provider"}.
            </p>
            <p>
              • <strong>Observation Count:</strong> {bars.length} historical daily bars available. 50+ observations are required for full moving average stability.
            </p>
            <p>
              • <strong>No Intraday Interpolation:</strong> Calculations use final daily closes. Intra-session candles during active market hours are excluded to prevent premature trend calculation.
            </p>
            <p>
              • <strong>Not Financial Advice:</strong> Technical indicators reflect mathematical aggregations of historical price action, not predictive guarantees of future performance.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
