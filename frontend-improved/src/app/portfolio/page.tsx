"use client";

import React, { useState, useEffect } from "react";
import { useStockData } from "@/lib/stock-context";
import {
  fetchProfilePortfolio,
  compareProfiles,
} from "@/lib/api";
import {
  PortfolioRiskMetrics,
  ProfileComparisonResponse,
} from "@/types";
import {
  Briefcase,
  ShieldAlert,
  ShieldCheck,
  Layers,
  ArrowRightLeft,
  CheckCircle2,
  AlertTriangle,
} from "lucide-react";

export default function PortfolioPage() {
  const { symbol, selectedProfileId, setSelectedProfileId, profiles } = useStockData();

  const [portfolio, setPortfolio] = useState<PortfolioRiskMetrics | null>(null);
  const [loading, setLoading] = useState(true);

  // Profile comparison state
  const [compSymbol, setCompSymbol] = useState(symbol || "NVDA");
  const [profileA, setProfileA] = useState("demo_profile_conservative");
  const [profileB, setProfileB] = useState("demo_profile_aggressive");
  const [compResult, setCompResult] = useState<ProfileComparisonResponse | null>(null);
  const [compLoading, setCompLoading] = useState(false);
  const [compError, setCompError] = useState<string | null>(null);

  useEffect(() => {
    async function loadPortfolio() {
      if (!selectedProfileId) return;
      setLoading(true);
      try {
        const data = await fetchProfilePortfolio(selectedProfileId);
        setPortfolio(data);
      } catch (err) {
        console.error("Failed to load portfolio:", err);
      } finally {
        setLoading(false);
      }
    }
    void loadPortfolio();
  }, [selectedProfileId]);

  const handleRunComparison = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!compSymbol.trim()) return;
    setCompLoading(true);
    setCompError(null);
    try {
      const res = await compareProfiles(compSymbol.trim().toUpperCase(), profileA, profileB);
      if (!res) {
        setCompError("Failed to run comparison. Ensure FastAPI backend is active.");
      } else {
        setCompResult(res);
      }
    } catch (err: unknown) {
      setCompError(err instanceof Error ? err.message : "Failed to compare profiles.");
    } finally {
      setCompLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800/80 pb-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-slate-100 sm:text-2xl flex items-center gap-2.5">
            <Briefcase className="h-6 w-6 text-emerald-400" />
            Investor Profile & Portfolio Risk Terminal
          </h1>
          <p className="mt-1 text-xs text-slate-400 sm:text-sm">
            Herfindahl-Hirschman Index (HHI) concentration analytics, portfolio holdings, and multi-profile suitability comparisons.
          </p>
        </div>

        {/* Profile Switcher */}
        {profiles.length > 0 && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-400">Active Profile:</span>
            <select
              value={selectedProfileId}
              onChange={(e) => setSelectedProfileId(e.target.value)}
              className="rounded-lg border border-slate-700/80 bg-slate-900 px-3 py-1.5 text-xs font-semibold text-slate-200 focus:border-emerald-500 focus:outline-none"
            >
              {profiles.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} (Risk: {p.risk_tolerance}/5)
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      <p className="rounded-lg border border-amber-500/20 bg-amber-500/5 px-4 py-3 text-xs text-amber-200/90">
        Demo investor profiles and seeded holdings are illustrative examples. They are not linked to brokerage accounts or live account balances.
      </p>

      {/* Profile Overview & Concentration Metric Cards */}
      {loading ? (
        <div className="flex h-40 items-center justify-center rounded-xl border border-slate-800/80 bg-[#111B2B]">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-emerald-400 border-t-transparent" />
        </div>
      ) : portfolio ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {/* Card 1: Risk Tolerance */}
          <div className="rounded-xl border border-slate-800/80 bg-[#111B2B] p-4">
            <span className="text-xs font-medium uppercase tracking-wider text-slate-500">
              Risk Tolerance & Horizon
            </span>
            <div className="mt-2 flex items-baseline justify-between">
              <span className="font-mono text-2xl font-bold text-slate-100">
                {portfolio.risk_tolerance} <span className="text-sm font-normal text-slate-400">/ 5</span>
              </span>
              <span className="rounded bg-slate-800/80 px-2 py-0.5 text-xs font-medium text-slate-300">
                {portfolio.investment_horizon_months} mos horizon
              </span>
            </div>
            <p className="mt-2 text-xs text-slate-400">{portfolio.investment_objective}</p>
          </div>

          {/* Card 2: HHI Concentration */}
          <div className="rounded-xl border border-slate-800/80 bg-[#111B2B] p-4">
            <span className="text-xs font-medium uppercase tracking-wider text-slate-500">
              Concentration (HHI Score)
            </span>
            <div className="mt-2 flex items-baseline justify-between">
              <span className="font-mono text-2xl font-bold text-slate-100">
                {portfolio.hhi_score.toFixed(3)}
              </span>
              <span
                className={`rounded px-2 py-0.5 text-xs font-semibold ${
                  portfolio.hhi_score > 0.25
                    ? "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                    : "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                }`}
              >
                {portfolio.hhi_score > 0.25 ? "High" : "Balanced"}
              </span>
            </div>
            <p className="mt-2 text-xs text-slate-400">{portfolio.concentration_level}</p>
          </div>

          {/* Card 3: Largest Position */}
          <div className="rounded-xl border border-slate-800/80 bg-[#111B2B] p-4">
            <span className="text-xs font-medium uppercase tracking-wider text-slate-500">
              Largest Position Weight
            </span>
            <div className="mt-2 flex items-baseline justify-between">
              <span className="font-mono text-2xl font-bold text-slate-100">
                {portfolio.largest_position_symbol || "—"}
              </span>
              <span className="font-mono text-sm text-slate-300">
                {(portfolio.largest_position_weight * 100).toFixed(1)}%
              </span>
            </div>
            <p className="mt-2 text-xs text-slate-400">
              Max single-asset limit: {(portfolio.max_allocation_limit * 100).toFixed(0)}%
            </p>
          </div>

          {/* Card 4: Allocation Status */}
          <div className="rounded-xl border border-slate-800/80 bg-[#111B2B] p-4">
            <span className="text-xs font-medium uppercase tracking-wider text-slate-500">
              Allocation Limit Check
            </span>
            <div className="mt-2 flex items-center gap-2">
              {portfolio.allocation_breached ? (
                <ShieldAlert className="h-6 w-6 text-amber-400" />
              ) : (
                <ShieldCheck className="h-6 w-6 text-emerald-400" />
              )}
              <span
                className={`font-semibold text-sm ${
                  portfolio.allocation_breached ? "text-amber-400" : "text-emerald-400"
                }`}
              >
                {portfolio.allocation_breached ? "Limit Exceeded" : "Within Guidelines"}
              </span>
            </div>
            <p className="mt-2 text-xs text-slate-400">
              {portfolio.holdings.length} active asset positions
            </p>
          </div>
        </div>
      ) : null}

      {/* Warnings Banner if any */}
      {portfolio && portfolio.warnings.length > 0 && (
        <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-xs text-amber-300 space-y-1">
          <div className="flex items-center gap-2 font-semibold">
            <AlertTriangle className="h-4 w-4 shrink-0 text-amber-400" />
            <span>Portfolio Risk Alerts</span>
          </div>
          {portfolio.warnings.map((w, idx) => (
            <p key={idx} className="pl-6 text-slate-300">• {w}</p>
          ))}
        </div>
      )}

      {/* Holdings Table */}
      {portfolio && (
        <div className="rounded-xl border border-slate-800/80 bg-[#111B2B] p-5">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400 mb-4 flex items-center gap-2">
            <Layers className="h-4 w-4 text-emerald-400" />
            Active Portfolio Positions ({portfolio.holdings.length})
          </h2>

          {portfolio.holdings.length === 0 ? (
            <div className="py-8 text-center text-xs text-slate-500">
              No positions recorded for this profile.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-500">
                    <th className="pb-3 font-medium">Asset / Ticker</th>
                    <th className="pb-3 font-medium">Asset Category</th>
                    <th className="pb-3 font-medium text-right">Shares</th>
                    <th className="pb-3 font-medium text-right">Cost Basis</th>
                    <th className="pb-3 font-medium text-right">Target Weight</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono">
                  {portfolio.holdings.map((h) => (
                    <tr key={h.id} className="hover:bg-slate-800/30 transition">
                      <td className="py-3 font-bold text-slate-200">{h.symbol}</td>
                      <td className="py-3 font-sans text-slate-400">{h.asset_category}</td>
                      <td className="py-3 text-right text-slate-300">{h.shares.toLocaleString()}</td>
                      <td className="py-3 text-right text-slate-300">
                        {h.cost_basis ? `$${h.cost_basis.toFixed(2)}` : "—"}
                      </td>
                      <td className="py-3 text-right font-bold text-emerald-400">
                        {(h.weight * 100).toFixed(1)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {portfolio && portfolio.watchlist.length > 0 && (
        <div className="rounded-xl border border-slate-800/80 bg-[#111B2B] p-5">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
            Watchlist ({portfolio.watchlist.length})
          </h2>
          <p className="mb-3 text-xs text-slate-500">
            Watchlist symbols are tracked for research and are not included in active-portfolio concentration metrics.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-800 text-slate-500">
                  <th className="pb-3 font-medium">Ticker</th>
                  <th className="pb-3 font-medium">Category</th>
                  <th className="pb-3 text-right font-medium">Reference weight</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono">
                {portfolio.watchlist.map((item) => (
                  <tr key={item.id}>
                    <td className="py-3 font-bold text-slate-200">{item.symbol}</td>
                    <td className="py-3 font-sans text-slate-400">{item.asset_category}</td>
                    <td className="py-3 text-right text-slate-400">{(item.weight * 100).toFixed(1)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Profile Comparison Demonstration Section */}
      <div className="rounded-xl border border-slate-800/80 bg-[#111B2B] p-5 space-y-4">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-2">
            <ArrowRightLeft className="h-4 w-4 text-emerald-400" />
            Deterministic Profile Comparison Tool (Live Hackathon Demonstration)
          </h2>
          <p className="mt-1 text-xs text-slate-400">
            Submit an identical market snapshot for a ticker to observe how FinWiseAI tailors suitability, risk emphasis, and diligence questions for different investor mandates without fabricating or altering underlying market observations.
          </p>
        </div>

        {/* Comparison Form */}
        <form onSubmit={handleRunComparison} className="flex flex-wrap items-center gap-3">
          <input
            type="text"
            value={compSymbol}
            onChange={(e) => setCompSymbol(e.target.value.toUpperCase())}
            placeholder="Stock Symbol..."
            className="w-32 rounded-lg border border-slate-700/80 bg-slate-900 px-3 py-1.5 text-xs font-semibold uppercase text-slate-200 focus:border-emerald-500 focus:outline-none"
          />

          <select
            value={profileA}
            onChange={(e) => setProfileA(e.target.value)}
            className="rounded-lg border border-slate-700/80 bg-slate-900 px-3 py-1.5 text-xs font-medium text-slate-200 focus:border-emerald-500 focus:outline-none"
          >
            {profiles.map((p) => (
              <option key={p.id} value={p.id}>
                Profile A: {p.name}
              </option>
            ))}
          </select>

          <span className="text-xs text-slate-500 font-bold">vs</span>

          <select
            value={profileB}
            onChange={(e) => setProfileB(e.target.value)}
            className="rounded-lg border border-slate-700/80 bg-slate-900 px-3 py-1.5 text-xs font-medium text-slate-200 focus:border-emerald-500 focus:outline-none"
          >
            {profiles.map((p) => (
              <option key={p.id} value={p.id}>
                Profile B: {p.name}
              </option>
            ))}
          </select>

          <button
            type="submit"
            disabled={compLoading}
            className="rounded-lg bg-emerald-500 px-4 py-1.5 text-xs font-semibold text-slate-950 transition hover:bg-emerald-400 disabled:opacity-50"
          >
            {compLoading ? "Evaluating..." : "Run Side-by-Side Comparison"}
          </button>
        </form>

        {compError && (
          <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-300">
            {compError}
          </div>
        )}

        {/* Comparison Result Cards */}
        {compResult && (
          <div className="mt-4 space-y-4 pt-3 border-t border-slate-800">
            <div className="flex items-center justify-between rounded-lg bg-emerald-500/10 border border-emerald-500/20 px-3 py-2 text-xs">
              <div className="flex items-center gap-2 text-emerald-400 font-semibold">
                <CheckCircle2 className="h-4 w-4" />
                <span>Underlying Market Data Snapshot Unaltered: 100% IDENTICAL</span>
              </div>
              <span className="font-mono text-slate-400">
                Ticker: {compResult.symbol} | Overall Status: {compResult.overall_status.toUpperCase()}
              </span>
            </div>

            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              {/* Profile A Output */}
              <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-bold text-slate-200">
                    {compResult.profile_a.profile_name}
                  </h3>
                  <span className="rounded bg-slate-800 px-2 py-0.5 text-xs text-slate-300">
                    Risk: {compResult.profile_a.risk_tolerance}/5
                  </span>
                </div>
                <div>
                  <span className="text-[11px] font-semibold text-slate-500 uppercase">
                    Mandate Suitability
                  </span>
                  <p className="font-semibold text-xs text-amber-400 mt-0.5">
                    {compResult.profile_a.suitability_rating}
                  </p>
                </div>
                <div>
                  <span className="text-[11px] font-semibold text-slate-500 uppercase">
                    Risk Emphasis
                  </span>
                  <p className="text-xs text-slate-300 mt-0.5 leading-relaxed">
                    {compResult.profile_a.risk_emphasis}
                  </p>
                </div>
                <div>
                  <span className="text-[11px] font-semibold text-slate-500 uppercase">
                    Portfolio Impact
                  </span>
                  <p className="text-xs text-slate-400 mt-0.5">
                    {compResult.profile_a.portfolio_impact_analysis}
                  </p>
                </div>
                <div>
                  <span className="text-[11px] font-semibold text-slate-500 uppercase">
                    Diligence Questions
                  </span>
                  <ul className="mt-1 space-y-1 text-xs text-slate-400">
                    {compResult.profile_a.suggested_investor_questions.map((q, idx) => (
                      <li key={idx} className="flex items-start gap-1.5">
                        <span className="text-emerald-400">•</span>
                        <span>{q}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>

              {/* Profile B Output */}
              <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-bold text-slate-200">
                    {compResult.profile_b.profile_name}
                  </h3>
                  <span className="rounded bg-slate-800 px-2 py-0.5 text-xs text-slate-300">
                    Risk: {compResult.profile_b.risk_tolerance}/5
                  </span>
                </div>
                <div>
                  <span className="text-[11px] font-semibold text-slate-500 uppercase">
                    Mandate Suitability
                  </span>
                  <p className="font-semibold text-xs text-emerald-400 mt-0.5">
                    {compResult.profile_b.suitability_rating}
                  </p>
                </div>
                <div>
                  <span className="text-[11px] font-semibold text-slate-500 uppercase">
                    Risk Emphasis
                  </span>
                  <p className="text-xs text-slate-300 mt-0.5 leading-relaxed">
                    {compResult.profile_b.risk_emphasis}
                  </p>
                </div>
                <div>
                  <span className="text-[11px] font-semibold text-slate-500 uppercase">
                    Portfolio Impact
                  </span>
                  <p className="text-xs text-slate-400 mt-0.5">
                    {compResult.profile_b.portfolio_impact_analysis}
                  </p>
                </div>
                <div>
                  <span className="text-[11px] font-semibold text-slate-500 uppercase">
                    Diligence Questions
                  </span>
                  <ul className="mt-1 space-y-1 text-xs text-slate-400">
                    {compResult.profile_b.suggested_investor_questions.map((q, idx) => (
                      <li key={idx} className="flex items-start gap-1.5">
                        <span className="text-emerald-400">•</span>
                        <span>{q}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
