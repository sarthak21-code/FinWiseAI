"use client";

import React, { useMemo } from "react";
import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Tooltip,
  Legend,
} from "recharts";
import { NewsArticle } from "@/types";

interface SentimentDistributionChartProps {
  articles: NewsArticle[];
}

export function SentimentDistributionChart({
  articles,
}: SentimentDistributionChartProps) {
  const { chartData, totalCount } = useMemo(() => {
    if (!articles || articles.length === 0) {
      return { chartData: [], totalCount: 0 };
    }

    let positive = 0;
    let negative = 0;
    let neutral = 0;

    for (const art of articles) {
      const label = art.sentiment_label?.toLowerCase();
      if (label === "positive") positive++;
      else if (label === "negative") negative++;
      else neutral++;
    }

    const data = [
      { name: "Positive", value: positive, color: "#34D399" },
      { name: "Neutral", value: neutral, color: "#FBBF24" },
      { name: "Negative", value: negative, color: "#F87171" },
    ].filter((item) => item.value > 0);

    return { chartData: data, totalCount: articles.length };
  }, [articles]);

  if (totalCount === 0) {
    return (
      <div className="flex h-56 w-full flex-col items-center justify-center rounded-xl border border-slate-800 bg-[#0D1421] p-6 text-center text-xs text-slate-500">
        <p>No processed news articles available for sentiment analysis.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col rounded-xl border border-slate-800/80 bg-[#0D1421] p-4 md:p-5">
      <div className="mb-2">
        <h3 className="text-sm font-bold tracking-tight text-slate-200">
          Headline Sentiment Distribution
        </h3>
        <p className="text-[11px] text-slate-400">
          Proportion of provider-sourced headlines ({totalCount} total; classification is heuristic)
        </p>
      </div>

      <div className="h-48 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={chartData}
              cx="50%"
              cy="50%"
              innerRadius={50}
              outerRadius={70}
              paddingAngle={4}
              dataKey="value"
            >
              {chartData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.color} />
              ))}
            </Pie>
            <Tooltip
              content={({ active, payload }) => {
                if (!active || !payload || !payload.length) return null;
                const d = payload[0].payload as { name: string; value: number };
                const pct = ((d.value / totalCount) * 100).toFixed(1);
                return (
                  <div className="rounded-lg border border-slate-700 bg-slate-900/95 p-2 shadow-xl backdrop-blur-md text-xs font-mono">
                    <p className="text-slate-200 font-bold">
                      {d.name}: {d.value} ({pct}%)
                    </p>
                  </div>
                );
              }}
            />
            <Legend
              verticalAlign="bottom"
              wrapperStyle={{ fontSize: "11px", paddingTop: "10px" }}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
