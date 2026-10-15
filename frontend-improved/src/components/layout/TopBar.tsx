"use client";

import React, { useState } from "react";
import { useStockData } from "@/lib/stock-context";
import { Search, RefreshCw, AlertCircle, Database, Clock, User } from "lucide-react";
import { formatDate, formatTradingDay } from "@/lib/formatting";

const POPULAR_TICKERS = ["AAPL", "MSFT", "NVDA", "GOOGL", "TSLA"];

export function TopBar() {
  const {
    symbol,
    setSelectedSymbol,
    quote,
    history,
    loading,
    error,
    refreshData,
    updatedAt,
    selectedProfileId,
    setSelectedProfileId,
    profiles,
    profileSetupError,
  } = useStockData();
  const [searchState, setSearchState] = useState({ symbol, value: symbol });
  const searchInput = searchState.symbol === symbol ? searchState.value : symbol;

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchInput.trim()) {
      setSelectedSymbol(searchInput.trim().toUpperCase());
    }
  };

  const tradingDay = quote?.latest_trading_day || history?.bars?.slice(-1)[0]?.trading_day;
  const isDemo = quote?.is_demo;
  const source = quote?.source || history?.source || "Provider Data";

  return (
    <header className="sticky top-0 z-30 flex flex-wrap items-center justify-between border-b border-slate-800/80 bg-[#080D16]/95 px-4 py-3 backdrop-blur-md md:px-6">
      {/* Left: Ticker Search & Presets */}
      <div className="flex flex-wrap items-center gap-3">
        <form onSubmit={handleSearch} className="relative flex items-center">
          <Search className="absolute left-3 h-4 w-4 text-slate-500" />
          <input
            type="text"
            value={searchInput}
            onChange={(e) => setSearchState({ symbol, value: e.target.value.toUpperCase() })}
            placeholder="Symbol (e.g. AAPL)..."
            className="w-40 rounded-lg border border-slate-700/80 bg-slate-900/90 py-1.5 pl-9 pr-3 text-sm font-semibold tracking-wide text-slate-100 placeholder:text-slate-600 focus:border-emerald-500/80 focus:outline-none focus:ring-1 focus:ring-emerald-500/50 sm:w-48"
          />
        </form>

        <div className="hidden items-center gap-1.5 sm:flex">
          {POPULAR_TICKERS.map((t) => (
            <button
              key={t}
              onClick={() => {
      setSearchState({ symbol, value: t });
                setSelectedSymbol(t);
              }}
              className={`rounded-md px-2 py-1 text-xs font-semibold transition ${
                symbol === t
                  ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
                  : "bg-slate-800/60 text-slate-400 hover:bg-slate-800 hover:text-slate-200"
              }`}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      {/* Right: Data Freshness, Provider Source & Refresh */}
      <div className="flex items-center gap-3 text-xs text-slate-400">
        {/* Source Badge */}
        <div className="hidden items-center gap-1.5 md:flex">
          <Database className="h-3.5 w-3.5 text-slate-500" />
          <span className="font-mono text-[11px] text-slate-300">{source}</span>
          {isDemo && (
            <span className="rounded bg-amber-500/10 px-1.5 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider text-amber-400 border border-amber-500/20">
              Demo Snapshot
            </span>
          )}
        </div>

        {/* Observation Date */}
        {tradingDay && (
          <div className="hidden items-center gap-1.5 lg:flex">
            <Clock className="h-3.5 w-3.5 text-slate-500" />
            <span>Close: <strong className="font-mono text-slate-200">{formatTradingDay(tradingDay)}</strong></span>
          </div>
        )}

        {/* Investor Profile Switcher */}
        {profiles && profiles.length > 0 && (
          <div className="flex items-center gap-1.5 rounded-lg border border-slate-700/80 bg-slate-900/90 px-2 py-1">
            <User className="h-3.5 w-3.5 text-emerald-400" />
            <select
              value={selectedProfileId}
              onChange={(e) => setSelectedProfileId(e.target.value)}
              className="bg-transparent text-xs font-medium text-slate-200 focus:outline-none cursor-pointer max-w-[170px] sm:max-w-[220px] truncate"
            >
              {profiles.map((p) => (
                <option key={p.id} value={p.id} className="bg-slate-900 text-slate-200">
                  {p.name} (Risk: {p.risk_tolerance}/5)
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Refresh Action */}
        <button
          onClick={refreshData}
          disabled={loading}
          title={updatedAt ? `Last fetched: ${formatDate(updatedAt)}` : "Refresh"}
          className="flex items-center gap-1.5 rounded-lg border border-slate-700/80 bg-slate-900/80 px-2.5 py-1.5 text-xs font-medium text-slate-300 transition hover:border-slate-600 hover:bg-slate-800 disabled:opacity-50"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin text-emerald-400" : ""}`} />
          <span className="hidden sm:inline">Refresh</span>
        </button>
      </div>

      {/* Global Error Banner if fatal */}
      {error && (
        <div className="mt-2 flex w-full items-center gap-2 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-300">
          <AlertCircle className="h-4 w-4 shrink-0 text-rose-400" />
          <span>{error}</span>
        </div>
      )}
      {profileSetupError && (
        <div
          role="alert"
          className="mt-2 flex w-full items-center gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-300"
        >
          <AlertCircle className="h-4 w-4 shrink-0 text-amber-400" />
          <span>{profileSetupError}</span>
        </div>
      )}
    </header>
  );
}
