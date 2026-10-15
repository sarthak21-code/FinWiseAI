"use client";

import React, { useState, useEffect } from "react";
import { fetchEvaluationMetrics } from "@/lib/api";
import { EvaluationMetrics } from "@/types";
import {
  BarChart3,
  Clock,
  CheckCircle2,
  Database,
  Cpu,
  Layers,
  Calendar,
  TrendingUp,
} from "lucide-react";

export default function EvaluationPage() {
  const [metrics, setMetrics] = useState<EvaluationMetrics | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadMetrics() {
      setLoading(true);
      try {
        const data = await fetchEvaluationMetrics();
        setMetrics(data);
      } catch (err) {
        console.error("Failed to load evaluation metrics:", err);
      } finally {
        setLoading(false);
      }
    }
    void loadMetrics();
  }, []);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="border-b border-slate-800/80 pb-4">
        <h1 className="text-xl font-bold tracking-tight text-slate-100 sm:text-2xl flex items-center gap-2.5">
          <BarChart3 className="h-6 w-6 text-emerald-400" />
          System Performance & Historical Signal Evaluation
        </h1>
        <p className="mt-1 text-xs text-slate-400 sm:text-sm">
          Monotonic execution latency tracking, 30-day forward return outcome evaluation, and audit logging.
        </p>
      </div>

      {loading ? (
        <div className="flex h-40 items-center justify-center rounded-xl border border-slate-800/80 bg-[#111B2B]">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-emerald-400 border-t-transparent" />
        </div>
      ) : metrics ? (
        <>
          {/* Key Metric Cards */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {/* Card 1: End-to-End Latency */}
            <div className="rounded-xl border border-slate-800/80 bg-[#111B2B] p-4">
              <span className="text-xs font-medium uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
                <Clock className="h-3.5 w-3.5 text-emerald-400" />
                Avg End-to-End Latency
              </span>
              <div className="mt-2 font-mono text-2xl font-bold text-slate-100">
                {metrics.average_total_latency_ms.toFixed(1)}{" "}
                <span className="text-xs font-normal text-slate-400">ms</span>
              </div>
              <p className="mt-1 text-xs text-slate-400">
                Concurrent execution across all agents
              </p>
            </div>

            {/* Card 2: RAG Retrieval Latency */}
            <div className="rounded-xl border border-slate-800/80 bg-[#111B2B] p-4">
              <span className="text-xs font-medium uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
                <Database className="h-3.5 w-3.5 text-blue-400" />
                Avg RAG BM25 Retrieval
              </span>
              <div className="mt-2 font-mono text-2xl font-bold text-slate-100">
                {metrics.average_rag_latency_ms.toFixed(1)}{" "}
                <span className="text-xs font-normal text-slate-400">ms</span>
              </div>
              <p className="mt-1 text-xs text-slate-400">
                Financial-document corpus BM25 retrieval & ranking
              </p>
            </div>

            {/* Card 3: 30-Day Forward Accuracy */}
            <div className="rounded-xl border border-slate-800/80 bg-[#111B2B] p-4">
              <span className="text-xs font-medium uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                Observed Real 30-Day Accuracy
              </span>
              <div className="mt-2 font-mono text-2xl font-bold text-emerald-400">
                {metrics.completed_windows_count === 0
                  ? "—"
                  : `${metrics.accuracy_rate_percent.toFixed(1)}%`}
              </div>
              <p className="mt-1 text-xs text-slate-400">
                {metrics.completed_windows_count === 0
                  ? "No eligible real outcomes yet"
                  : `${metrics.accurate_signals_count} of ${metrics.completed_windows_count} completed windows`}
              </p>
            </div>

            {/* Card 4: Evaluation Coverage */}
            <div className="rounded-xl border border-slate-800/80 bg-[#111B2B] p-4">
              <span className="text-xs font-medium uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
                <Calendar className="h-3.5 w-3.5 text-amber-400" />
                Evaluation Records
              </span>
              <div className="mt-2 font-mono text-2xl font-bold text-slate-100">
                {metrics.total_signals_evaluated}
              </div>
              <p className="mt-1 text-xs text-slate-400">
                {metrics.completed_windows_count} evaluated • {metrics.pending_windows_count} pending • {metrics.unavailable_windows_count} unavailable • {metrics.excluded_windows_count} excluded
              </p>
            </div>
          </div>

          {/* Per-Agent Latency Breakdown */}
          {metrics.agent_latencies && Object.keys(metrics.agent_latencies).length > 0 && (
            <div className="rounded-xl border border-slate-800/80 bg-[#111B2B] p-5">
              <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400 mb-4 flex items-center gap-2">
                <Cpu className="h-4 w-4 text-emerald-400" />
                Agent Execution Latency Breakdown (Monotonic perf_counter)
              </h2>

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {Object.entries(metrics.agent_latencies).map(([agentName, lat]) => (
                  <div key={agentName} className="rounded-lg bg-slate-900/60 p-3 border border-slate-800">
                    <span className="text-xs text-slate-400 font-medium">{agentName}</span>
                    <div className="mt-1 font-mono text-lg font-bold text-slate-200">
                      {lat.toFixed(1)} <span className="text-xs font-normal text-slate-500">ms</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Historical Signal Evaluation Table */}
          <div className="rounded-xl border border-slate-800/80 bg-[#111B2B] p-5">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400 mb-4 flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-emerald-400" />
              Historical 30-Day Forward Return Evaluation Log
            </h2>
            <p className="mb-4 text-xs text-slate-400">
              Accuracy uses only outcomes marked as real. Synthetic demonstration records are labeled in the table and excluded from accuracy.
              {` ${metrics.synthetic_signals_evaluated} synthetic examples (${metrics.synthetic_completed_windows_count} completed, ${metrics.synthetic_pending_windows_count} pending).`}
            </p>
            <p className="mb-4 text-xs text-slate-500">
              Unavailable outcomes remain retryable and do not count as incorrect. Matured outcomes update only when an authorized operator invokes the protected updater; recurring scheduling is not configured.
            </p>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-500">
                    <th className="pb-3 font-medium">Symbol / Source</th>
                    <th className="pb-3 font-medium">Dimension</th>
                    <th className="pb-3 font-medium">Signal</th>
                    <th className="pb-3 font-medium">Signal Date</th>
                    <th className="pb-3 font-medium text-right">Entry Price</th>
                    <th className="pb-3 font-medium text-right">Exit Price</th>
                    <th className="pb-3 font-medium text-right">Actual 30d Return</th>
                    <th className="pb-3 font-medium text-center">Evaluation Outcome</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono">
                  {metrics.evaluation_history.map((e) => (
                    <tr key={e.id} className="hover:bg-slate-800/30 transition">
                      <td className="py-3 font-bold text-slate-200">
                        {e.symbol}
                        {e.is_synthetic && (
                          <span className="ml-2 rounded border border-amber-500/20 bg-amber-500/10 px-1.5 py-0.5 font-sans text-[9px] font-semibold uppercase text-amber-400">
                            Synthetic demo
                          </span>
                        )}
                      </td>
                      <td className="py-3 font-sans text-slate-400 uppercase text-[11px]">{e.dimension}</td>
                      <td className="py-3 font-sans">
                        <span
                          className={`rounded px-1.5 py-0.5 text-[10px] font-bold uppercase ${
                            e.classification === "bullish"
                              ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                              : e.classification === "bearish"
                              ? "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                              : "bg-slate-800 text-slate-300"
                          }`}
                        >
                          {e.classification}
                        </span>
                      </td>
                      <td className="py-3 text-slate-400">{e.signal_date}</td>
                      <td className="py-3 text-right text-slate-300">${e.entry_price.toFixed(2)}</td>
                      <td className="py-3 text-right text-slate-300">
                        {e.exit_price ? `$${e.exit_price.toFixed(2)}` : "—"}
                      </td>
                      <td className="py-3 text-right font-bold">
                        {e.actual_return_percent !== null && e.actual_return_percent !== undefined ? (
                          <span className={e.actual_return_percent >= 0 ? "text-emerald-400" : "text-rose-400"}>
                            {e.actual_return_percent >= 0 ? "+" : ""}
                            {e.actual_return_percent.toFixed(2)}%
                          </span>
                        ) : (
                          <span className="text-slate-500 italic font-sans">Outcome pending</span>
                        )}
                      </td>
                      <td className="py-3 text-center">
                        <span
                          className={`rounded px-2 py-0.5 text-[10px] font-bold uppercase ${
                            e.status === "evaluated" && e.outcome === "accurate"
                              ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                              : e.status === "pending"
                              ? "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                              : e.status === "unavailable"
                              ? "bg-sky-500/10 text-sky-300 border border-sky-500/20"
                              : e.status === "excluded" || e.outcome === "inconclusive"
                              ? "bg-slate-800 text-slate-300 border border-slate-700"
                              : "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                          }`}
                        >
                          {e.status === "evaluated"
                            ? `evaluated: ${e.outcome}`
                            : e.status.replace("_", " ")}
                        </span>
                        {e.status === "unavailable" && e.status_detail && (
                          <p className="mt-1 max-w-64 text-center font-sans text-[10px] text-slate-500">
                            {e.status_detail}
                          </p>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Recent Analysis Sessions Audit Trail */}
          {metrics.recent_sessions && metrics.recent_sessions.length > 0 && (
            <div className="rounded-xl border border-slate-800/80 bg-[#111B2B] p-5">
              <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400 mb-4 flex items-center gap-2">
                <Layers className="h-4 w-4 text-emerald-400" />
                Recent Intelligence Sessions Audit Trail
              </h2>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-mono">
                  <thead>
                    <tr className="border-b border-slate-800 text-slate-500 font-sans">
                      <th className="pb-3 font-medium">Session ID</th>
                      <th className="pb-3 font-medium">Symbol</th>
                      <th className="pb-3 font-medium">Status</th>
                      <th className="pb-3 font-medium">Analysis completeness</th>
                      <th className="pb-3 font-medium text-right">RAG Latency</th>
                      <th className="pb-3 font-medium text-right">Total Latency</th>
                      <th className="pb-3 font-medium text-right">Evaluations (done / pending / unavailable / excluded)</th>
                      <th className="pb-3 font-medium text-right">Executed At</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {metrics.recent_sessions.map((s) => (
                      <tr key={s.id} className="hover:bg-slate-800/30 transition">
                        <td className="py-3 text-slate-400 text-[11px] truncate max-w-[120px]">{s.id}</td>
                        <td className="py-3 font-bold text-slate-200">{s.symbol}</td>
                        <td className="py-3 font-sans">
                          <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] text-slate-300">
                            {s.overall_classification}
                          </span>
                        </td>
                        <td className="py-3 font-sans">
                          <span className={`rounded px-1.5 py-0.5 text-[10px] uppercase ${
                            s.analysis_completeness === "complete"
                              ? "bg-emerald-500/10 text-emerald-300"
                              : s.analysis_completeness === "partial"
                              ? "bg-amber-500/10 text-amber-300"
                              : "bg-slate-800 text-slate-400"
                          }`}>
                            {s.analysis_completeness}
                          </span>
                        </td>
                        <td className="py-3 text-right text-blue-400">{s.rag_latency_ms.toFixed(1)} ms</td>
                        <td className="py-3 text-right text-emerald-400">{s.total_latency_ms.toFixed(1)} ms</td>
                        <td className="py-3 text-right text-slate-400">
                          {s.evaluation_status_counts.evaluated} / {s.evaluation_status_counts.pending} / {s.evaluation_status_counts.unavailable} / {s.evaluation_status_counts.excluded}
                        </td>
                        <td className="py-3 text-right text-slate-400">{s.created_at.slice(0, 19).replace("T", " ")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      ) : null}
    </div>
  );
}
