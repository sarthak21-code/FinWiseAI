"use client";

import React from "react";
import { useStockData } from "@/lib/stock-context";
import { SectionHeader, MetricCard, StatusBadge } from "@/components/shared/CommonComponents";
import {
  formatCurrency,
  formatSignedPercent,
  formatDate,
} from "@/lib/formatting";
import {
  Building2,
  ShieldCheck,
  Info,
} from "lucide-react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Cell,
} from "recharts";

export default function FundamentalsPage() {
  const { symbol, fundamental, intelligence } = useStockData();

  const fundamentalAgent = intelligence?.assessments?.find((a) =>
    a.agent_name.includes("Fundamental"),
  );

  const currency = fundamental?.currency || "USD";
  const revenue = fundamental?.revenue ?? null;
  const netIncome = fundamental?.net_income ?? null;
  const revGrowth = fundamental?.revenue_growth_percent ?? null;
  const netMargin = fundamental?.net_margin_percent ?? null;
  const roe = fundamental?.return_on_equity_percent ?? null;
  const peRatio = fundamental?.pe_ratio ?? null;
  const eps = fundamental?.eps ?? null;
  const currentRatio = fundamental?.current_ratio ?? null;
  const debtToEquity = fundamental?.debt_to_equity ?? null;

  // Visual comparison of key fundamental ratios
  const ratioComparisonData = [
    { name: "Net Margin", value: netMargin, unit: "%", benchmark: "15% Healthy" },
    { name: "Return on Equity", value: roe, unit: "%", benchmark: "15% Strong" },
    { name: "Revenue Growth", value: revGrowth, unit: "%", benchmark: "YoY" },
  ].filter((d) => d.value !== null && Number.isFinite(d.value));

  return (
    <div className="space-y-6">
      <SectionHeader
        eyebrow="Fundamental Engine"
        title={`Fundamental Analysis — ${symbol}`}
        description="Corporate financial metrics from the configured provider. Reporting periods may vary by metric and are shown only when supplied."
        rightAction={<StatusBadge status={fundamentalAgent?.status || "neutral"} />}
      />

      {/* Corporate Metadata Banner */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-800/80 bg-[#0D1421] p-4 text-xs">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-500/10 border border-indigo-500/30 text-indigo-400">
            <Building2 size={18} />
          </div>
          <div>
            <h3 className="font-bold text-slate-100 text-sm">
              {fundamental?.company_name || `${symbol} Financial Statement Metrics`}
            </h3>
            <p className="text-slate-400 font-mono text-[11px]">
              Reporting Period: {fundamental?.fiscal_period || "Not supplied"} / {fundamental?.fiscal_year || "Not supplied"} • Currency: {currency}
            </p>
          </div>
        </div>

        <div className="text-right text-[11px] text-slate-400 font-mono">
          <div>Source: {fundamental?.source || "Awaiting provider response"}</div>
          <div>Retrieved: {formatDate(fundamental?.fetched_at_utc)}</div>
        </div>
      </div>

      {/* SECTION A: Key Fundamental Metrics */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <MetricCard
          label="Trailing P/E"
          value={peRatio !== null ? `${peRatio.toFixed(2)}x` : "—"}
          tone={peRatio !== null ? (peRatio < 25 ? "positive" : "warning") : "neutral"}
          subtext="Price-to-Earnings"
        />
        <MetricCard
          label="Net Margin"
          value={netMargin !== null ? `${netMargin.toFixed(2)}%` : "—"}
          tone={netMargin !== null ? (netMargin >= 15 ? "positive" : netMargin > 0 ? "warning" : "negative") : "neutral"}
          subtext="Net income / Revenue"
        />
        <MetricCard
          label="ROE"
          value={roe !== null ? `${roe.toFixed(2)}%` : "—"}
          tone={roe !== null ? (roe >= 15 ? "positive" : "neutral") : "neutral"}
          subtext="Return on equity"
        />
        <MetricCard
          label="Revenue Growth"
          value={revGrowth !== null ? formatSignedPercent(revGrowth) : "—"}
          tone={revGrowth !== null ? (revGrowth >= 0 ? "positive" : "negative") : "neutral"}
          subtext="YoY revenue delta"
        />
        <MetricCard
          label="Current Ratio"
          value={currentRatio !== null ? `${currentRatio.toFixed(2)}` : "—"}
          tone={currentRatio !== null ? (currentRatio >= 1.0 ? "positive" : "negative") : "neutral"}
          subtext="Short-term liquidity"
        />
        <MetricCard
          label="Diluted EPS"
          value={eps !== null ? formatCurrency(eps, currency) : "—"}
          subtext="Earnings per share"
        />
      </div>

      {/* SECTION B & C: Profitability & Statement Overview */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Profitability & Margin Visual Comparison */}
        <div className="rounded-xl border border-slate-800/80 bg-[#0D1421] p-5">
          <h3 className="text-sm font-bold tracking-tight text-slate-200 mb-1">
            Profitability & Growth Profile
          </h3>
          <p className="text-[11px] text-slate-400 mb-4">
            Visual comparison of normalized performance metrics. Note that margins and growth measure distinct financial dimensions.
          </p>

          {ratioComparisonData.length > 0 ? (
            <div className="h-48 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={ratioComparisonData} layout="vertical" margin={{ top: 10, right: 30, left: 20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" horizontal={false} />
                  <XAxis type="number" stroke="#64748B" fontSize={10} tickFormatter={(v) => `${v}%`} />
                  <YAxis type="category" dataKey="name" stroke="#64748B" fontSize={11} tickLine={false} axisLine={false} />
                  <Tooltip
                    content={({ active, payload }) => {
                      if (!active || !payload || !payload.length) return null;
                      const d = payload[0].payload as { name: string; value: number; unit: string; benchmark: string };
                      return (
                        <div className="rounded-lg border border-slate-700 bg-slate-900/95 p-2 shadow-xl backdrop-blur-md text-xs font-mono">
                          <p className="text-slate-300 font-bold">{d.name}: {d.value.toFixed(2)}{d.unit}</p>
                          <p className="text-slate-500 text-[10px]">{d.benchmark}</p>
                        </div>
                      );
                    }}
                  />
                  <Bar dataKey="value" fill="#6366F1" radius={[0, 4, 4, 0]}>
                    {ratioComparisonData.map((entry, index) => {
                      const val = Number(entry.value ?? 0);
                      return (
                        <Cell
                          key={`cell-${index}`}
                          fill={val >= 15 ? "#34D399" : val > 0 ? "#818CF8" : "#F87171"}
                        />
                      );
                    })}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="flex h-48 items-center justify-center text-xs text-slate-500 italic">
              No quantitative ratio observations returned for this asset.
            </div>
          )}
        </div>

        {/* Statement Totals & Capital Structure */}
        <div className="rounded-xl border border-slate-800/80 bg-[#0D1421] p-5">
          <h3 className="text-sm font-bold tracking-tight text-slate-200 mb-1">
            Financial Scale & Liquidity Profile
          </h3>
          <p className="text-[11px] text-slate-400 mb-4">
            Balance sheet and top-line metrics returned by the configured data provider
          </p>

          <div className="space-y-3 text-xs">
            <div className="flex items-center justify-between border-b border-slate-800/60 pb-2">
              <span className="text-slate-400">Total Top-Line Revenue:</span>
              <span className="font-mono font-bold text-slate-100">
                {revenue !== null ? formatCurrency(revenue, currency) : "—"}
              </span>
            </div>
            <div className="flex items-center justify-between border-b border-slate-800/60 pb-2">
              <span className="text-slate-400">Net Operating Income:</span>
              <span className="font-mono font-bold text-slate-100">
                {netIncome !== null ? formatCurrency(netIncome, currency) : "—"}
              </span>
            </div>
            <div className="flex items-center justify-between border-b border-slate-800/60 pb-2">
              <span className="text-slate-400">Debt to Equity Ratio:</span>
              <span className="font-mono font-bold text-slate-100">
                {debtToEquity !== null ? `${debtToEquity.toFixed(2)}` : "—"}
              </span>
            </div>
            <div className="flex items-center justify-between border-b border-slate-800/60 pb-2">
              <span className="text-slate-400">Current Liquidity Ratio:</span>
              <span className="font-mono font-bold text-slate-100">
                {currentRatio !== null ? `${currentRatio.toFixed(2)}` : "—"}
              </span>
            </div>
          </div>

          <div className="mt-4 flex items-start gap-2 rounded-lg border border-slate-800/80 bg-slate-900/60 p-2.5 text-[11px] text-slate-400">
            <Info size={14} className="shrink-0 text-slate-500 mt-0.5" />
            <span>
              <strong>Valuation Notice:</strong> FinWiseAI does not invent simulated discounted cash flow (DCF) target prices or claim intrinsic fair value. P/E and margin multiples provide factual comparison points rather than speculative price targets.
            </span>
          </div>
        </div>
      </div>

      {/* SECTION G & H: Fundamental Evidence & Agent Assessment */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="rounded-xl border border-slate-800/80 bg-[#0D1421] p-5">
          <div className="flex items-center gap-2 text-slate-200 mb-3 font-semibold text-sm">
            <Building2 size={16} className="text-indigo-400" />
            <span>Fundamental Agent Findings & Logic</span>
          </div>

          <div className="space-y-3">
            <p className="text-xs text-slate-300 leading-relaxed">
              {fundamentalAgent?.summary || "Fundamental assessment evaluating operational margins and balance sheet strength."}
            </p>

            {(fundamentalAgent?.evidence || []).length > 0 && (
              <ul className="space-y-1.5 border-t border-slate-800/60 pt-3">
                {fundamentalAgent?.evidence.map((ev, idx) => (
                  <li key={idx} className="flex items-start gap-2 text-xs text-slate-300">
                    <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-indigo-400" />
                    <span>{ev}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        <div className="rounded-xl border border-slate-800/80 bg-[#0D1421] p-5">
          <div className="flex items-center gap-2 text-amber-400 mb-3 font-semibold text-sm">
            <ShieldCheck size={16} />
            <span>Data Freshness & Reporting Limitations</span>
          </div>

          <div className="space-y-2.5 text-xs text-slate-400 leading-relaxed">
            <p>
              • <strong>Periodic Lag:</strong> Fundamental financial statements are reported on quarterly (10-Q) and annual (10-K) cycles. Trailing numbers do not reflect unannounced intra-quarter developments.
            </p>
            <p>
              • <strong>Multi-Source Caveat:</strong> Ratios derived from public market quotes and filing statements can vary between accounting standards (GAAP vs. Non-GAAP).
            </p>
            <p>
              • <strong>Warnings:</strong> {fundamental?.data_warnings?.length ? fundamental.data_warnings.join(" ") : "No reporting irregularities reported by provider."}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
