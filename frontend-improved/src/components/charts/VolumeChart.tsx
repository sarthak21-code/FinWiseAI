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
} from "recharts";
import { HistoricalBar } from "@/types";
import { formatCompactNumber } from "@/lib/formatting";

interface VolumeChartProps {
  bars: HistoricalBar[];
}

export function VolumeChart({ bars }: VolumeChartProps) {
  const chartData = useMemo(() => {
    if (!bars || bars.length === 0) return [];

    return bars
      .filter((b) => b.volume !== null && b.volume !== undefined)
      .slice(-60)
      .map((b) => ({
        trading_day: b.trading_day,
        volume: b.volume,
        close: b.close,
      }));
  }, [bars]);

  if (!chartData || chartData.length === 0) {
    return (
      <div className="flex h-44 w-full flex-col items-center justify-center rounded-xl border border-slate-800 bg-[#0D1421] p-6 text-center text-xs text-slate-500">
        <p>No historical volume observations provided by the current data source.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col rounded-xl border border-slate-800/80 bg-[#0D1421] p-4 md:p-5">
      <div className="mb-2">
        <h3 className="text-sm font-bold tracking-tight text-slate-200">
          Historical Trading Volume
        </h3>
        <p className="text-[11px] text-slate-400">
          Reported daily share turnover aligned to identical trading sessions
        </p>
      </div>

      <div className="h-40 w-full">
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
              tickFormatter={(v: number) => formatCompactNumber(v)}
            />
            <Tooltip
              content={({ active, payload }) => {
                if (!active || !payload || !payload.length) return null;
                const d = payload[0].payload as { trading_day: string; volume: number };
                return (
                  <div className="rounded-lg border border-slate-700 bg-slate-900/95 p-2 shadow-xl backdrop-blur-md text-xs font-mono">
                    <p className="text-slate-400">{d.trading_day}</p>
                    <p className="text-cyan-400 font-bold mt-1">
                      Volume: {d.volume.toLocaleString()} shares
                    </p>
                  </div>
                );
              }}
            />
            <Bar dataKey="volume" fill="#38BDF8" fillOpacity={0.6} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
