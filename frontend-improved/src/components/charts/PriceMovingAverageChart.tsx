"use client";

import React, { useMemo } from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from "recharts";
import { HistoricalBar } from "@/types";
import { formatCurrency } from "@/lib/formatting";

interface PriceMovingAverageChartProps {
  bars: HistoricalBar[];
  currency?: string;
}

export function PriceMovingAverageChart({
  bars,
  currency = "USD",
}: PriceMovingAverageChartProps) {
  const chartData = useMemo(() => {
    if (!bars || bars.length === 0) return [];

    return bars.map((bar, index) => {
      // SMA 20: average of last 20 closes ending at index
      let sma20: number | null = null;
      if (index >= 19) {
        const slice = bars.slice(index - 19, index + 1);
        sma20 = slice.reduce((sum, b) => sum + b.close, 0) / 20;
      }

      // SMA 50: average of last 50 closes ending at index
      let sma50: number | null = null;
      if (index >= 49) {
        const slice = bars.slice(index - 49, index + 1);
        sma50 = slice.reduce((sum, b) => sum + b.close, 0) / 50;
      }

      return {
        trading_day: bar.trading_day,
        close: bar.close,
        sma_20: sma20 !== null ? Number(sma20.toFixed(2)) : null,
        sma_50: sma50 !== null ? Number(sma50.toFixed(2)) : null,
      };
    });
  }, [bars]);

  const minPrice = useMemo(() => {
    if (chartData.length === 0) return 0;
    const prices = chartData.map((d) => d.close);
    return Math.floor(Math.min(...prices) * 0.96);
  }, [chartData]);

  const maxPrice = useMemo(() => {
    if (chartData.length === 0) return 0;
    const prices = chartData.map((d) => d.close);
    return Math.ceil(Math.max(...prices) * 1.04);
  }, [chartData]);

  if (!bars || bars.length < 20) {
    return (
      <div className="flex h-72 w-full flex-col items-center justify-center rounded-xl border border-slate-800 bg-[#0D1421] p-6 text-center text-xs text-slate-500">
        <p>Insufficient observations to render moving average overlays.</p>
        <p className="mt-1 text-[11px] text-slate-600">
          At least 20 historical sessions are required.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col rounded-xl border border-slate-800/80 bg-[#0D1421] p-4 md:p-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-bold tracking-tight text-slate-200">
            Trend Benchmark: Close vs SMA 20 & SMA 50
          </h3>
          <p className="text-[11px] text-slate-400">
            Strict observation alignment: Moving averages are only calculated after sufficient periods exist
          </p>
        </div>
      </div>

      <div className="h-72 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
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
                const d = payload[0].payload as {
                  trading_day: string;
                  close: number;
                  sma_20: number | null;
                  sma_50: number | null;
                };
                return (
                  <div className="rounded-lg border border-slate-700 bg-slate-900/95 p-3 shadow-xl backdrop-blur-md text-xs font-mono">
                    <p className="text-slate-400">{d.trading_day}</p>
                    <p className="text-slate-100 font-bold mt-1">
                      Close: {formatCurrency(d.close, currency)}
                    </p>
                    <p className="text-amber-400">
                      SMA 20: {d.sma_20 !== null ? formatCurrency(d.sma_20, currency) : "N/A (insufficient obs)"}
                    </p>
                    <p className="text-blue-400">
                      SMA 50: {d.sma_50 !== null ? formatCurrency(d.sma_50, currency) : "N/A (insufficient obs)"}
                    </p>
                  </div>
                );
              }}
            />
            <Legend
              verticalAlign="top"
              align="right"
              wrapperStyle={{ paddingBottom: "10px", fontSize: "11px" }}
            />
            <Line
              type="monotone"
              dataKey="close"
              name="Price Close"
              stroke="#F1F5F9"
              strokeWidth={1.5}
              dot={false}
            />
            <Line
              type="monotone"
              dataKey="sma_20"
              name="SMA 20"
              stroke="#FBBF24"
              strokeWidth={1.5}
              dot={false}
              connectNulls={false}
            />
            <Line
              type="monotone"
              dataKey="sma_50"
              name="SMA 50"
              stroke="#60A5FA"
              strokeWidth={1.5}
              dot={false}
              connectNulls={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
