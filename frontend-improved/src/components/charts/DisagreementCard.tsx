"use client";

import React from "react";
import { AgentDisagreement } from "@/types";
import { AlertTriangle, GitFork, ShieldAlert } from "lucide-react";

interface DisagreementCardProps {
  disagreements: AgentDisagreement[];
}

export function DisagreementCard({ disagreements }: DisagreementCardProps) {
  if (!disagreements || disagreements.length === 0) {
    return (
      <div className="rounded-xl border border-slate-800/80 bg-[#0D1421] p-5">
        <div className="flex items-center gap-2.5 text-emerald-400">
          <GitFork size={18} />
          <h3 className="text-sm font-bold text-slate-200">
            No Opposing Directional Conflicts Detected
          </h3>
        </div>
        <p className="mt-2 text-xs leading-relaxed text-slate-400">
          The analytical agents do not hold directly contradictory directional stances (e.g. Bullish vs. Bearish).
          Assessments either align in orientation or reflect non-directional conditions (Neutral or Insufficient Data).
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {disagreements.map((item, idx) => {
        const cleanEvidence = (item.evidence || []).filter((e) => e && e.trim().length > 0);
        const isHigh = item.significance === "high";

        return (
          <div
            key={idx}
            className={`rounded-xl border p-5 transition-all ${
              isHigh
                ? "border-amber-500/40 bg-amber-500/5"
                : "border-slate-800 bg-[#0D1421]"
            }`}
          >
            {/* Header Badge & Agents */}
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800/60 pb-3">
              <div className="flex items-center gap-2">
                <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-400">
                  <AlertTriangle size={15} />
                </span>
                <div>
                  <h4 className="text-xs font-bold uppercase tracking-wider text-amber-300">
                    Agent Disagreement Intelligence
                  </h4>
                  <p className="text-[11px] font-semibold text-slate-200">
                    {item.agents.join(" ⚡ vs. ⚡ ")}
                  </p>
                </div>
              </div>

              <span
                className={`rounded px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider ${
                  isHigh
                    ? "bg-rose-500/20 text-rose-300 border border-rose-500/30"
                    : "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                }`}
              >
                Significance: {item.significance}
              </span>
            </div>

            {/* Core Conflict Statement */}
            <div className="mt-3">
              <p className="text-xs font-semibold text-slate-200 leading-relaxed">
                {item.conflict}
              </p>
            </div>

            {/* Conflicting Evidence Points */}
            {cleanEvidence.length > 0 && (
              <div className="mt-3 rounded-lg border border-slate-800/80 bg-slate-950/60 p-3">
                <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-2">
                  Underlying Divergent Evidence
                </p>
                <ul className="space-y-1.5">
                  {cleanEvidence.map((ev, eIdx) => (
                    <li key={eIdx} className="flex items-start gap-2 text-xs text-slate-300 leading-relaxed">
                      <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-400" />
                      <span>{ev}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Methodological Value Interpretation */}
            <div className="mt-3 flex items-start gap-2 text-[11px] text-slate-400 leading-relaxed">
              <ShieldAlert size={14} className="text-slate-500 shrink-0 mt-0.5" />
              <span>
                <strong>System Governance:</strong> FinWiseAI preserves this conflict rather than mathematically averaging contradictory signals into a false consensus. Investors should evaluate whether technical momentum or fundamental valuation is their dominant horizon.
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
