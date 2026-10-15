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
  ReferenceLine,
} from "recharts";
import { HistoricalBar } from "@/types";

interface RsiChartProps {
  bars: HistoricalBar[];
  currentRsi?: number | null;
}

export function RsiChart({ bars, currentRsi }: RsiChartProps) {
  // Calculate historical RSI(14) series matching backend formula
  const chartData = useMemo(() => {
    if (!bars || bars.length < 15) return [];

    const closes = bars.map((b) => b.close);
    const results: { trading_day: string; rsi: number | null }[] = [];

    for (let i = 0; i < bars.length; i++) {
      if (i < 14) {
        results.push({ trading_day: bars[i].trading_day, rsi: null });
        continue;
      }

      const recent = closes.slice(i - 14, i + 1);
      const changes: number[] = [];
      for (let j = 1; j < recent.length; j++) {
        changes.push(recent[j] - recent[j - 1]);
      }

      const gains = changes.map((c) => (c > 0 ? c : 0));
      const losses = changes.map((c) => (c < 0 ? -c : 0));

      const avgGain = gains.reduce((a, b) => a + b, 0) / 14;
      const avgLoss = losses.reduce((a, b) => a + b, 0) / 14;

      if (avgLoss === 0) {
        results.push({
          trading_day: bars[i].trading_day,
          rsi: avgGain > 0 ? 100 : 50,
        });
      } else {
        const rs = avgGain / avgLoss;
        const val = 100 - 100 / (1 + rs);
        results.push({
          trading_day: bars[i].trading_day,
          rsi: Number(val.toFixed(2)),
        });
      }
    }

    return results;
  }, [bars]);

  const displayRsi =
    currentRsi !== undefined && currentRsi !== null
      ? currentRsi.toFixed(2)
      : chartData.length > 0 && chartData[chartData.length - 1].rsi !== null
        ? chartData[chartData.length - 1].rsi?.toFixed(2)
        : "—";

  if (!bars || bars.length < 15) {
    return (
      <div className="flex h-56 w-full flex-col items-center justify-center rounded-xl border border-slate-800 bg-[#0D1421] p-6 text-center text-xs text-slate-500">
        <p>Insufficient observations to calculate RSI (14 periods required).</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col rounded-xl border border-slate-800/80 bg-[#0D1421] p-4 md:p-5">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-bold tracking-tight text-slate-200">
            Relative Strength Index (RSI 14)
          </h3>
          <p className="text-[11px] text-slate-400">
            Oscillator bounded [0, 100]. Reference lines at 30 (oversold convention) & 70 (overbought convention).
          </p>
        </div>
        <div className="font-mono text-xl font-bold text-emerald-400">
          {displayRsi}
        </div>
      </div>

      <div className="h-48 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
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
              domain={[0, 100]}
              ticks={[0, 30, 50, 70, 100]}
              stroke="#64748B"
              fontSize={10}
              tickLine={false}
              axisLine={false}
            />
            <ReferenceLine y={70} stroke="#F87171" strokeDasharray="4 4" strokeWidth={1} label={{ value: "70", fill: "#F87171", fontSize: 10, position: "right" }} />
            <ReferenceLine y={30} stroke="#34D399" strokeDasharray="4 4" strokeWidth={1} label={{ value: "30", fill: "#34D399", fontSize: 10, position: "right" }} />
            <Tooltip
              content={({ active, payload }) => {
                if (!active || !payload || !payload.length) return null;
                const d = payload[0].payload as { trading_day: string; rsi: number | null };
                return (
                  <div className="rounded-lg border border-slate-700 bg-slate-900/95 p-2 shadow-xl backdrop-blur-md text-xs font-mono">
                    <p className="text-slate-400">{d.trading_day}</p>
                    <p className="text-emerald-400 font-bold mt-1">
                      RSI(14): {d.rsi !== null ? d.rsi : "N/A"}
                    </p>
                  </div>
                );
              }}
            />
            <Line
              type="monotone"
              dataKey="rsi"
              stroke="#A78BFA"
              strokeWidth={2}
              dot={false}
              connectNulls={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-2 text-[10px] text-slate-500">
        *Thresholds represent standard quantitative conventions, not a guarantee of future reversal or trading outcome.
      </p>
    </div>
  );
}
