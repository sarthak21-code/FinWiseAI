"use client";

import React, { useState, useMemo } from "react";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";
import { HistoricalBar } from "@/types";
import { formatCurrency } from "@/lib/formatting";

type RangeOption = "1M" | "3M" | "6M" | "ALL";

interface PriceHistoryChartProps {
  bars: HistoricalBar[];
  currency?: string;
  sourceNote?: string;
}

export function PriceHistoryChart({
  bars,
  currency = "USD",
  sourceNote,
}: PriceHistoryChartProps) {
  const [selectedRange, setSelectedRange] = useState<RangeOption>("6M");

  const filteredBars = useMemo(() => {
    if (!bars || bars.length === 0) return [];

    if (selectedRange === "1M") return bars.slice(-21);
    if (selectedRange === "3M") return bars.slice(-63);
    if (selectedRange === "6M") return bars.slice(-126);
    return bars;
  }, [bars, selectedRange]);

  const minPrice = useMemo(() => {
    if (filteredBars.length === 0) return 0;
    const prices = filteredBars.map((b) => b.close);
    return Math.floor(Math.min(...prices) * 0.98);
  }, [filteredBars]);

  const maxPrice = useMemo(() => {
    if (filteredBars.length === 0) return 0;
    const prices = filteredBars.map((b) => b.close);
    return Math.ceil(Math.max(...prices) * 1.02);
  }, [filteredBars]);

  if (!bars || bars.length === 0) {
    return (
      <div className="flex h-72 w-full flex-col items-center justify-center rounded-xl border border-slate-800 bg-[#0D1421] p-6 text-center text-xs text-slate-500">
        <p>No historical closing prices available for this asset.</p>
        <p className="mt-1 text-[11px] text-slate-600">Synthetic data is not substituted.</p>
      </div>
    );
  }

  const isUpTrend =
    filteredBars.length > 1 &&
    filteredBars[filteredBars.length - 1].close >= filteredBars[0].close;

  const strokeColor = isUpTrend ? "#34D399" : "#F87171";
  const gradientId = `priceGradient-${isUpTrend ? "up" : "down"}`;

  return (
    <div className="flex flex-col rounded-xl border border-slate-800/80 bg-[#0D1421] p-4 md:p-5">
      {/* Chart Top Controls */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-bold tracking-tight text-slate-200">
            Historical Price Movement
          </h3>
          <p className="text-[11px] text-slate-400">
            Available completed daily closes ({filteredBars.length} observations)
          </p>
        </div>

        {/* Range Buttons */}
        <div className="flex items-center gap-1 rounded-lg border border-slate-800 bg-slate-900/80 p-0.5">
          {(["1M", "3M", "6M", "ALL"] as RangeOption[]).map((range) => {
            const isAvailable =
              range === "1M"
                ? bars.length >= 10
                : range === "3M"
                  ? bars.length >= 30
                  : true;

            return (
              <button
                key={range}
                onClick={() => setSelectedRange(range)}
                disabled={!isAvailable}
                className={`rounded px-2.5 py-1 font-mono text-[11px] font-semibold transition ${
                  selectedRange === range
                    ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
                    : "text-slate-400 hover:text-slate-200 disabled:opacity-30"
                }`}
              >
                {range}
              </button>
            );
          })}
        </div>
      </div>

      {/* Recharts Area Container */}
      <div className="h-64 sm:h-72 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={filteredBars} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
            <defs>
              <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={strokeColor} stopOpacity={0.3} />
                <stop offset="95%" stopColor={strokeColor} stopOpacity={0.0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" vertical={false} />
            <XAxis
              dataKey="trading_day"
              stroke="#64748B"
              fontSize={10}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v: string) => {
                const parts = v.split("-");
                return parts.length === 3 ? `${parts[1]}/${parts[2]}` : v;
              }}
            />
            <YAxis
              domain={[minPrice, maxPrice]}
              stroke="#64748B"
              fontSize={10}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v: number) => `$${v.toFixed(0)}`}
            />
            <Tooltip
              content={({ active, payload }) => {
                if (!active || !payload || !payload.length) return null;
                const data = payload[0].payload as HistoricalBar;
                return (
                  <div className="rounded-lg border border-slate-700 bg-slate-900/95 p-2.5 shadow-xl backdrop-blur-md">
                    <p className="font-mono text-[11px] font-semibold text-slate-400">
                      {data.trading_day}
                    </p>
                    <p className="mt-1 font-mono text-sm font-bold text-slate-100">
                      Close: {formatCurrency(data.close, currency)}
                    </p>
                    {data.open && (
                      <p className="font-mono text-[10px] text-slate-400">
                        Open: {formatCurrency(data.open, currency)} | High:{" "}
                        {formatCurrency(data.high, currency)} | Low:{" "}
                        {formatCurrency(data.low, currency)}
                      </p>
                    )}
                    {data.volume && (
                      <p className="font-mono text-[10px] text-slate-400">
                        Vol: {data.volume.toLocaleString()}
                      </p>
                    )}
                  </div>
                );
              }}
            />
            <Area
              type="monotone"
              dataKey="close"
              stroke={strokeColor}
              strokeWidth={2}
              fillOpacity={1}
              fill={`url(#${gradientId})`}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {sourceNote && (
        <div className="mt-3 text-[10px] text-slate-500 font-mono flex items-center justify-between">
          <span>Source: {sourceNote}</span>
          <span>End of Day Session</span>
        </div>
      )}
    </div>
  );
}
