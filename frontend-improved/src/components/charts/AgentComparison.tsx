"use client";

import React from "react";
import { AgentAssessment } from "@/types";
import { StatusBadge } from "@/components/shared/CommonComponents";
import { Activity, Building2, Newspaper, ChevronRight, ShieldCheck } from "lucide-react";
import { useSearchParams } from "next/navigation";

interface AgentComparisonProps {
  assessments: AgentAssessment[];
}

export function AgentComparison({ assessments }: AgentComparisonProps) {
  const searchParams = useSearchParams();
  const ticker = searchParams.get("ticker");
  const queryStr = ticker ? `?ticker=${encodeURIComponent(ticker)}` : "";

  const getAgentIcon = (name: string) => {
    if (name.includes("Technical")) return <Activity size={18} className="text-cyan-400" />;
    if (name.includes("Fundamental")) return <Building2 size={18} className="text-indigo-400" />;
    return <Newspaper size={18} className="text-amber-400" />;
  };

  const getAgentHref = (name: string) => {
    if (name.includes("Technical")) return `/technical${queryStr}`;
    if (name.includes("Fundamental")) return `/fundamentals${queryStr}`;
    return `/news${queryStr}`;
  };

  if (!assessments || assessments.length === 0) {
    return (
      <div className="rounded-xl border border-slate-800 bg-[#0D1421] p-6 text-center text-xs text-slate-500">
        No agent assessments returned from the intelligence engine.
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
      {assessments.map((agent) => {
        const cleanEvidence = (agent.evidence || []).filter((e) => e && e.trim().length > 0);
        const cleanLimitations = (agent.limitations || []).filter((l) => l && l.trim().length > 0);

        return (
          <div
            key={agent.agent_name}
            className="flex flex-col justify-between rounded-xl border border-slate-800/80 bg-[#0D1421] p-4 transition-all hover:border-slate-700/80"
          >
            <div>
              {/* Header */}
              <div className="flex items-center justify-between gap-2 border-b border-slate-800/60 pb-3">
                <div className="flex items-center gap-2.5">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-900 border border-slate-800">
                    {getAgentIcon(agent.agent_name)}
                  </div>
                  <div>
                    <h4 className="text-xs font-bold text-slate-200">{agent.agent_name}</h4>
                    <p className="text-[10px] text-slate-500 font-mono truncate max-w-[140px]">
                      {agent.source}
                    </p>
                  </div>
                </div>
                <StatusBadge status={agent.status} />
              </div>

              {/* Summary */}
              <p className="mt-3 text-xs leading-relaxed text-slate-300 min-h-[48px]">
                {agent.summary || "No assessment summary returned."}
              </p>

              <div className="mt-3 grid grid-cols-2 gap-2 border-t border-slate-800/60 pt-3 text-[10px]">
                <div>
                  <span className="text-slate-500">Heuristic confidence</span>
                  <p className="font-mono text-slate-300">
                    {typeof agent.confidence === "number" ? `${(agent.confidence * 100).toFixed(0)}%` : "Not reported"}
                  </p>
                </div>
                <div>
                  <span className="text-slate-500">Measured agent time</span>
                  <p className="font-mono text-slate-300">
                    {typeof agent.latency_ms === "number" ? `${agent.latency_ms.toFixed(1)} ms` : "Not reported"}
                  </p>
                </div>
                {agent.confidence_method && (
                  <p className="col-span-2 text-slate-500">
                    {agent.confidence_method} Not a calibrated probability.
                  </p>
                )}
              </div>

              {/* Evidence highlights */}
              <div className="mt-3 space-y-1.5 border-t border-slate-800/60 pt-3">
                <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                  Key Supporting Evidence
                </p>
                {cleanEvidence.length > 0 ? (
                  <ul className="space-y-1">
                    {cleanEvidence.slice(0, 3).map((item, idx) => (
                      <li key={idx} className="flex items-start gap-1.5 text-[11px] text-slate-400 leading-tight">
                        <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-emerald-400" />
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-[11px] italic text-slate-600">
                    No supporting evidence was returned for this assessment.
                  </p>
                )}
              </div>

              {/* Limitations preview */}
              {cleanLimitations.length > 0 && (
                <div className="mt-3 rounded-lg border border-slate-800/80 bg-slate-950/40 p-2 text-[10px] text-slate-500">
                  <div className="flex items-center gap-1 font-semibold text-slate-400 mb-0.5">
                    <ShieldCheck size={12} className="text-slate-500" />
                    <span>Primary Limitation</span>
                  </div>
                  <p className="line-clamp-2">{cleanLimitations[0]}</p>
                </div>
              )}
            </div>

            {/* Bottom Drill-down Link */}
            <div className="mt-4 pt-3 border-t border-slate-800/60 flex items-center justify-between text-[11px]">
              <span className="text-[10px] font-mono text-slate-600 uppercase">
                {agent.is_demo
                  ? "Synthetic demo"
                  : agent.status === "unavailable"
                    ? "Unavailable"
                    : "Reported source; not independently verified"}
              </span>
              <a
                href={getAgentHref(agent.agent_name)}
                className="flex items-center gap-1 font-medium text-emerald-400 hover:text-emerald-300 transition"
              >
                <span>Examine Agent</span>
                <ChevronRight size={13} />
              </a>
            </div>
          </div>
        );
      })}
    </div>
  );
}
