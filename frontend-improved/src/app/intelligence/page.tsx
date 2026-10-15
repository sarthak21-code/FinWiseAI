"use client";

import React, { useState } from "react";
import { useStockData } from "@/lib/stock-context";
import { SectionHeader, StatusBadge } from "@/components/shared/CommonComponents";
import { AgentComparison } from "@/components/charts/AgentComparison";
import { DisagreementCard } from "@/components/charts/DisagreementCard";
import {
  Brain,
  GitFork,
  Cpu,
  Clock,
  FileText,
  UserCheck,
  ChevronDown,
  ChevronUp,
  Layers,
  HelpCircle,
  ExternalLink,
} from "lucide-react";
import { formatDate } from "@/lib/formatting";

export default function IntelligencePage() {
  const { symbol, intelligence } = useStockData();

  const assessments = intelligence?.assessments || [];
  const disagreements = intelligence?.disagreements || [];
  const overallStatus = intelligence?.overall_status || "insufficient_data";
  const analysisCompleteness = intelligence?.analysis_completeness || "partial";
  const citations = intelligence?.citations || [];
  const signals = intelligence?.signals || [];
  const reasoningTrace = intelligence?.reasoning_trace || [];
  const personalized = intelligence?.personalized_interpretation;

  const [traceExpanded, setTraceExpanded] = useState(true);

  // Evidence completeness
  const availableAgents = assessments.filter(
    (a) => !a.is_demo && ["bullish", "bearish", "neutral"].includes(a.status),
  ).length;
  const directionalAgents = assessments.filter(
    (a) => a.status === "bullish" || a.status === "bearish",
  ).length;

  return (
    <div className="space-y-6">
      <SectionHeader
        eyebrow="Signature Differentiator"
        title={`Multi-Agent Intelligence & Disagreement Engine — ${symbol}`}
        description="FinWiseAI runs independent deterministic analysis services concurrently. Rather than averaging contradictory signals, it surfaces conflicts, retrieves related financial-document context without treating lexical matches as proof, and personalizes risk context."
        rightAction={<StatusBadge status={overallStatus} />}
      />

      {analysisCompleteness === "partial" && (
        <div
          role="status"
          className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 text-xs text-amber-100"
        >
          Partial analysis: one or more specialist agents returned unavailable,
          insufficient, or synthetic data. Review each agent status and warning
          before interpreting the consensus verdict.
        </div>
      )}

      {/* SECTION A: Overall Status & Aggregation Decision */}
      <div className="rounded-xl border border-slate-800/80 bg-[#0D1421] p-5">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800/60 pb-3">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
              <Brain size={22} />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-100">
                Consensus Verdict: {overallStatus.toUpperCase()}
              </h3>
              <p className="text-xs text-slate-400 font-mono">
                Evaluated: {formatDate(intelligence?.generated_at_utc)}
              </p>
            </div>
          </div>

          {/* Latency & Provenance Tag */}
          <div className="flex items-center gap-3">
            {intelligence?.total_latency_ms !== undefined && (
              <span className="flex items-center gap-1 rounded bg-slate-800/80 px-2 py-1 font-mono text-xs text-slate-300">
                <Clock className="h-3.5 w-3.5 text-emerald-400" />
                {intelligence.total_latency_ms.toFixed(1)} ms
              </span>
            )}
            <StatusBadge status={overallStatus} />
          </div>
        </div>

        <p className="mt-4 text-xs leading-relaxed text-slate-300 max-w-4xl">
          {intelligence?.analysis_note ||
            "FinWiseAI aggregation engine evaluates directional consistency across technical, fundamental, and news sentiment inputs."}
        </p>

        {/* Evidence Quality & Latency Summary */}
        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-5 rounded-lg border border-slate-800/80 bg-slate-950/60 p-3 text-xs">
          <div>
            <span className="text-slate-500 text-[11px]">Analysis completeness:</span>
            <p className="font-mono text-base font-bold text-slate-100">
              {analysisCompleteness === "complete" ? "Complete" : "Partial"}
            </p>
          </div>
          <div>
            <span className="text-slate-500 text-[11px]">Active Agents:</span>
            <p className="font-mono text-base font-bold text-slate-100">
              {availableAgents} / 3
            </p>
          </div>
          <div>
            <span className="text-slate-500 text-[11px]">Directional Views:</span>
            <p className="font-mono text-base font-bold text-slate-100">
              {directionalAgents}
            </p>
          </div>
          <div>
            <span className="text-slate-500 text-[11px]">Direct Conflicts:</span>
            <p className="font-mono text-base font-bold text-amber-400">
              {disagreements.length}
            </p>
          </div>
          <div>
            <span className="text-slate-500 text-[11px]">RAG Citations:</span>
            <p className="font-mono text-base font-bold text-blue-400">
              {citations.length} Retrieved passages
            </p>
          </div>
        </div>

        <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4 rounded-lg border border-slate-800/80 bg-slate-950/60 p-3 text-xs">
          <div>
            <span className="text-slate-500 text-[11px]">Analysis duration</span>
            <p className="font-mono text-base font-bold text-slate-100">
              {intelligence?.total_latency_ms !== undefined ? `${intelligence.total_latency_ms.toFixed(1)} ms` : "Not measured"}
            </p>
            <span className="text-[10px] text-slate-600">From analysis start through synthesis; excludes persistence.</span>
          </div>
          <div>
            <span className="text-slate-500 text-[11px]">BM25 search duration</span>
            <p className="font-mono text-base font-bold text-slate-100">
              {intelligence?.rag_latency_ms !== undefined ? `${intelligence.rag_latency_ms.toFixed(1)} ms` : "Not measured"}
            </p>
            <span className="text-[10px] text-slate-600">Claim preparation and document search.</span>
          </div>
          <div>
            <span className="text-slate-500 text-[11px]">Lexical evidence coverage</span>
            <p className="font-mono text-base font-bold text-slate-100">
              {intelligence?.evidence_coverage_percent == null ? "Unavailable" : `${intelligence.evidence_coverage_percent.toFixed(1)}%`}
            </p>
            <span className="text-[10px] text-slate-600">Claims with a BM25 context match / claims searched. Not factual support.</span>
          </div>
          <div>
            <span className="text-slate-500 text-[11px]">Claims with context</span>
            <p className="font-mono text-base font-bold text-slate-100">
              {intelligence?.evidence_cited_claims_count ?? 0} / {intelligence?.evidence_claims_count ?? 0}
            </p>
            <span className="text-[10px] text-slate-600">A failed search is reported as unavailable, not 0% coverage.</span>
          </div>
        </div>
      </div>

      {intelligence?.data_warnings && intelligence.data_warnings.length > 0 && (
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-4 text-xs text-amber-100">
          <h3 className="font-semibold">Data and execution limitations</h3>
          <ul className="mt-2 space-y-1 text-amber-100/80">
            {intelligence.data_warnings.map((warning, index) => <li key={index}>• {warning}</li>)}
          </ul>
        </div>
      )}

      {/* SECTION B: Personalized Mandate Context */}
      {personalized && (
        <div className="rounded-xl border border-slate-800/80 bg-[#111B2B] p-5 space-y-3">
          <div className="flex items-center justify-between border-b border-slate-800/60 pb-3">
            <div className="flex items-center gap-2 text-sm font-bold text-slate-100">
              <UserCheck className="h-4 w-4 text-emerald-400" />
              <span>Personalized Mandate Context — {personalized.profile_name}</span>
            </div>
            <span className="rounded bg-slate-800 px-2 py-0.5 text-xs text-slate-300">
              Risk Tolerance: {personalized.risk_tolerance} / 5
            </span>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-3 text-xs">
            <div className="rounded-lg bg-slate-900/60 p-3 border border-slate-800">
              <span className="text-[11px] font-semibold text-slate-500 uppercase">Suitability</span>
              <p className="font-bold text-sm text-emerald-400 mt-1">
                {personalized.suitability_rating}
              </p>
            </div>
            <div className="rounded-lg bg-slate-900/60 p-3 border border-slate-800 md:col-span-2">
              <span className="text-[11px] font-semibold text-slate-500 uppercase">Risk Emphasis</span>
              <p className="text-xs text-slate-300 mt-1 leading-relaxed">
                {personalized.risk_emphasis}
              </p>
            </div>
          </div>

          {personalized.suggested_investor_questions.length > 0 && (
            <div className="rounded-lg bg-slate-900/40 p-3 border border-slate-800/60">
              <span className="text-[11px] font-semibold text-slate-400 flex items-center gap-1.5 uppercase">
                <HelpCircle className="h-3.5 w-3.5 text-emerald-400" />
                Tailored Due-Diligence Questions
              </span>
              <ul className="mt-2 space-y-1.5 text-xs text-slate-300">
                {personalized.suggested_investor_questions.map((q, idx) => (
                  <li key={idx} className="flex items-start gap-2">
                    <span className="text-emerald-400 font-bold">•</span>
                    <span>{q}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* SECTION C: Multi-Dimensional Signals */}
      {signals.length > 0 && (
        <div className="rounded-xl border border-slate-800/80 bg-[#111B2B] p-5">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-2">
            <Layers className="h-4 w-4 text-emerald-400" />
            Independent Signal Classifications
          </h3>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {signals.map((sig) => (
              <div
                key={sig.signal_id}
                className="rounded-lg border border-slate-800 bg-slate-900/60 p-3 space-y-2 text-xs"
              >
                <div className="flex items-center justify-between">
                  <span className="font-bold text-slate-200 capitalize">
                    {sig.dimension.replace("_", " ")}
                  </span>
                  <StatusBadge status={sig.classification} />
                </div>
                <div className="flex items-center justify-between font-mono text-[11px] text-slate-400">
                  <span>Confidence:</span>
                  <span className="font-bold text-slate-200">
                    {(sig.confidence * 100).toFixed(0)}%
                  </span>
                </div>
                <p className="text-[11px] text-slate-400 leading-snug">
                  {sig.evidence[0] || sig.confidence_method}
                </p>
                <p className="text-[10px] text-slate-600">
                  Heuristic confidence: {sig.confidence_method} Not a calibrated probability.
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* SECTION D: Signature Disagreement Intelligence */}
      <div>
        <div className="mb-3 flex items-center justify-between">
          <div>
            <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
              <GitFork size={18} className="text-amber-400" />
              <span>Agent Disagreement Intelligence</span>
            </h3>
            <p className="text-xs text-slate-400">
              Detection of analytical divergence between technical price momentum, fundamental valuation, and news sentiment.
            </p>
          </div>
        </div>
        <DisagreementCard disagreements={disagreements} />
      </div>

      {/* SECTION E: Agent Evidence Cards */}
      <div>
        <div className="mb-3">
          <h3 className="text-base font-bold text-slate-100">
            Independent Agent Evidence Cards
          </h3>
          <p className="text-xs text-slate-400">
            Full evidence points, data sources, latency, and limitations for each constituent analytical agent
          </p>
        </div>
        <AgentComparison assessments={assessments} />
      </div>

      {/* SECTION F: Financial Documents & Grounded Citations (RAG) */}
      <>
        <div className="rounded-xl border border-slate-800/80 bg-[#111B2B] p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div>
              <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-2">
                <FileText className="h-4 w-4 text-emerald-400" />
                Retrieved Document Context (RAG)
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                BM25 relevance indicates lexical similarity only. It does not establish factual support or detect contradiction. Synthetic documents remain labeled.
              </p>
            </div>
            <span className="rounded bg-blue-500/10 px-2 py-0.5 text-xs font-semibold text-blue-400 border border-blue-500/20">
              BM25 Lexical Ranking
            </span>
          </div>

          {citations.length > 0 ? (
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {citations.map((cite) => (
              <div
                key={cite.citation_id}
                className="rounded-lg border border-slate-800 bg-slate-900/60 p-4 space-y-2 text-xs"
              >
                <div className="flex items-center justify-between">
                  <span className="font-bold text-slate-200">{cite.document_title}</span>
                  <span
                    className={`rounded px-1.5 py-0.5 text-[10px] font-bold uppercase ${
                      cite.synthetic
                        ? "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                        : "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                    }`}
                  >
                    {cite.synthetic ? "Synthetic Demo" : (cite.source_name || "Source")}
                  </span>
                </div>

                <div className="text-[11px] font-medium text-slate-300 flex items-center gap-1.5">
                  <HelpCircle className="h-3.5 w-3.5 shrink-0 text-slate-400" />
                  <span>Retrieved context for claim (support not assessed): {cite.claim}</span>
                </div>

                <blockquote className="border-l-2 border-slate-700 pl-2.5 italic text-slate-300 text-xs leading-relaxed bg-slate-950/40 p-2 rounded">
                  &ldquo;{cite.excerpt}&rdquo;
                </blockquote>

                <div className="flex items-center justify-between text-[11px] text-slate-500 font-mono">
                  <span>Period: {cite.reporting_period}</span>
                  <span>BM25 relevance: {cite.relevance_score.toFixed(3)}</span>
                  <span>Chunk: {cite.chunk_id.slice(0, 8)}</span>
                  {cite.source_url && (
                    <a
                      href={cite.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-emerald-400 hover:underline flex items-center gap-1 font-sans"
                    >
                      Open Source <ExternalLink size={10} />
                    </a>
                  )}
                </div>
              </div>
            ))}
            </div>
          ) : (
            <p className="rounded-lg border border-slate-800 bg-slate-900/50 p-4 text-xs text-slate-400">
              No document context was attached to this analysis. See the data and execution limitations above for whether search returned no matches or could not run. No citation was fabricated.
            </p>
          )}
        </div>
      </>

      {/* SECTION G: Step-by-Step Reasoning Trace */}
      {reasoningTrace.length > 0 && (
        <div className="rounded-xl border border-slate-800/80 bg-[#0D1421] p-5">
          <div
            onClick={() => setTraceExpanded(!traceExpanded)}
            className="flex items-center justify-between cursor-pointer text-slate-200 font-semibold text-sm"
          >
            <div className="flex items-center gap-2">
              <Cpu size={16} className="text-emerald-400" />
              <span>Deterministic Execution & Reasoning Trace ({reasoningTrace.length} Steps)</span>
            </div>
            {traceExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </div>

          {traceExpanded && (
            <div className="mt-4 space-y-3 border-t border-slate-800 pt-3 text-xs">
              {reasoningTrace.map((step) => (
                <div key={step.step_number} className="flex items-start gap-3">
                  <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-slate-800 text-[10px] font-mono text-emerald-400 font-bold">
                    {step.step_number}
                  </span>
                  <div className="space-y-0.5">
                    <strong className="text-slate-200">{step.title}</strong>
                    <p className="text-slate-400 text-[11px] leading-relaxed">
                      {step.description}
                    </p>
                    <p className="text-emerald-400/90 text-[11px] font-mono">
                      &rarr; {step.outcome}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
