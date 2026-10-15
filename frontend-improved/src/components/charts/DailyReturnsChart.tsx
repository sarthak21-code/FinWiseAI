"use client";

import React, { useMemo } from "react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Cell,
  ReferenceLine,
} from "recharts";
import { HistoricalBar } from "@/types";
import { formatSignedPercent } from "@/lib/formatting";

interface DailyReturnsChartProps {
  bars: HistoricalBar[];
}

export function DailyReturnsChart({ bars }: DailyReturnsChartProps) {
  const chartData = useMemo(() => {
    if (!bars || bars.length < 2) return [];

    const results: { trading_day: string; returnPercent: number }[] = [];
    for (let i = 1; i < bars.length; i++) {
      const prev = bars[i - 1].close;
      const curr = bars[i].close;
      if (prev > 0) {
        const ret = ((curr / prev) - 1) * 100;
        results.push({
          trading_day: bars[i].trading_day,
          returnPercent: Number(ret.toFixed(2)),
        });
      }
    }
    // Limit to recent 60 trading days for legibility
    return results.slice(-60);
  }, [bars]);

  if (!bars || bars.length < 2) {
    return (
      <div className="flex h-56 w-full flex-col items-center justify-center rounded-xl border border-slate-800 bg-[#0D1421] p-6 text-center text-xs text-slate-500">
        <p>Insufficient observations to calculate daily percentage returns.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col rounded-xl border border-slate-800/80 bg-[#0D1421] p-4 md:p-5">
      <div className="mb-3">
        <h3 className="text-sm font-bold tracking-tight text-slate-200">
          Daily Return Distribution (Recent 60 Sessions)
        </h3>
        <p className="text-[11px] text-slate-400">
          Day-over-day price variation calculated from consecutive available closing observations.
        </p>
      </div>

      <div className="h-48 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
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
              stroke="#64748B"
              fontSize={10}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v: number) => `${v}%`}
            />
            <ReferenceLine y={0} stroke="#475569" strokeWidth={1} />
            <Tooltip
              content={({ active, payload }) => {
                if (!active || !payload || !payload.length) return null;
                const d = payload[0].payload as { trading_day: string; returnPercent: number };
                const isPos = d.returnPercent >= 0;
                return (
                  <div className="rounded-lg border border-slate-700 bg-slate-900/95 p-2 shadow-xl backdrop-blur-md text-xs font-mono">
                    <p className="text-slate-400">{d.trading_day}</p>
                    <p className={`font-bold mt-1 ${isPos ? "text-emerald-400" : "text-rose-400"}`}>
                      Return: {formatSignedPercent(d.returnPercent)}
                    </p>
                  </div>
                );
              }}
            />
            <Bar dataKey="returnPercent">
              {chartData.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={entry.returnPercent >= 0 ? "#34D399" : "#F87171"}
                  fillOpacity={0.8}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
