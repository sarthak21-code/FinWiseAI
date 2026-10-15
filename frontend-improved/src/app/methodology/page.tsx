"use client";

import React from "react";
import { useStockData } from "@/lib/stock-context";
import { SectionHeader } from "@/components/shared/CommonComponents";
import {
  Database,
  Calculator,
  ShieldAlert,
  Layers,
  FileText,
} from "lucide-react";

export default function MethodologyPage() {
  const { quote, history, fundamental, intelligence } = useStockData();

  return (
    <div className="space-y-6">
      <SectionHeader
        eyebrow="Transparency & Integrity"
        title="Data Sources, Calculation Methodology & System Specifications"
        description="How this deterministic research prototype sources market data, calculates indicators, retrieves document context, tailors risk interpretation, and records pending evaluations."
      />

      {/* SECTION A & B: Data Sources & Provenance */}
      <div className="rounded-xl border border-slate-800/80 bg-[#0D1421] p-5">
        <div className="flex items-center gap-2 text-slate-200 mb-3 font-semibold text-sm">
          <Database size={16} className="text-emerald-400" />
          <span>Configured Data Ingestion Architecture</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 text-xs">
          <div className="rounded-lg border border-slate-800/80 bg-slate-900/60 p-3.5 space-y-1.5">
            <h4 className="font-bold text-slate-200">Historical & Daily Quotes</h4>
            <p className="text-slate-400 text-[11px]">
              <strong>Primary:</strong> Alpha Vantage TIME_SERIES_DAILY
            </p>
            <p className="text-slate-400 text-[11px]">
              <strong>Fallback:</strong> Yahoo Finance (yfinance daily OHLCV)
            </p>
            <p className="text-slate-500 text-[10px]">
              Active Source: {quote?.source || history?.source || "Provider Data"}
            </p>
          </div>

          <div className="rounded-lg border border-slate-800/80 bg-slate-900/60 p-3.5 space-y-1.5">
            <h4 className="font-bold text-slate-200">Financial-Document RAG</h4>
            <p className="text-slate-400 text-[11px]">
              <strong>Corpus:</strong> Seeded passages are synthetic filing-style examples. Internally supplied documents retain metadata; no public SEC ingestion route exists.
            </p>
            <p className="text-slate-400 text-[11px]">
              <strong>Retrieval:</strong> Lexical BM25 ranking with chunk indexing
            </p>
            <p className="text-slate-500 text-[10px]">
              Retrieval: Related passages with provenance; BM25 does not prove claim entailment
            </p>
          </div>

          <div className="rounded-lg border border-slate-800/80 bg-slate-900/60 p-3.5 space-y-1.5">
            <h4 className="font-bold text-slate-200">Fundamental Metrics</h4>
            <p className="text-slate-400 text-[11px]">
              <strong>Source:</strong> Yahoo Finance company information via yfinance
            </p>
            <p className="text-slate-400 text-[11px]">
              <strong>Integrity:</strong> Null preservation; missing fields are never zeroed
            </p>
            <p className="text-slate-500 text-[10px]">
              Active Source: {fundamental?.source || "Awaiting provider response"}
            </p>
          </div>

          <div className="rounded-lg border border-slate-800/80 bg-slate-900/60 p-3.5 space-y-1.5">
            <h4 className="font-bold text-slate-200">News Sentiment & Signals</h4>
            <p className="text-slate-400 text-[11px]">
              <strong>Pipeline:</strong> Lexical scoring with entity relevance filtering
            </p>
            <p className="text-slate-400 text-[11px]">
              <strong>Signals:</strong> Momentum, volume anomaly, sentiment & health
            </p>
            <p className="text-slate-500 text-[10px]">
              Articles Loaded: {intelligence?.news_articles?.length || 0}
            </p>
          </div>
        </div>
      </div>

      {/* SECTION C: Quantitative Formulas */}
      <div className="rounded-xl border border-slate-800/80 bg-[#0D1421] p-5">
        <div className="flex items-center gap-2 text-slate-200 mb-3 font-semibold text-sm">
          <Calculator size={16} className="text-cyan-400" />
          <span>Quantitative Specifications & Formulas</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
          <div className="rounded-lg border border-slate-800/80 bg-slate-900/50 p-3.5">
            <h4 className="font-bold text-slate-200 mb-1">Simple Moving Averages (SMA)</h4>
            <p className="text-slate-400 text-[11px] font-mono mb-2">
              SMA_n = (sum of last n closes) / n
            </p>
            <p className="text-slate-400 text-[11px] leading-relaxed">
              Calculated for n = 20 and n = 50. Observations before n periods have elapsed are preserved as null rather than fabricated.
            </p>
          </div>

          <div className="rounded-lg border border-slate-800/80 bg-slate-900/50 p-3.5">
            <h4 className="font-bold text-slate-200 mb-1">Relative Strength Index (RSI 14)</h4>
            <p className="text-slate-400 text-[11px] font-mono mb-2">
              RS = avg_gain / avg_loss; RSI = 100 - (100 / (1 + RS))
            </p>
            <p className="text-slate-400 text-[11px] leading-relaxed">
              Standard 14-period lookback. Zero-loss edge case safely yields 100.0 (or 50.0 if zero change).
            </p>
          </div>

          <div className="rounded-lg border border-slate-800/80 bg-slate-900/50 p-3.5">
            <h4 className="font-bold text-slate-200 mb-1">Portfolio Concentration (HHI)</h4>
            <p className="text-slate-400 text-[11px] font-mono mb-2">
              HHI = sum(w_i^2) for normalized weights w_i
            </p>
            <p className="text-slate-400 text-[11px] leading-relaxed">
              Herfindahl-Hirschman Index across portfolio holdings. HHI &lt; 0.15 denotes diversified; 0.15-0.25 moderate; &gt; 0.25 high cluster risk.
            </p>
          </div>
        </div>
      </div>

      {/* SECTION D: Financial-Document RAG Pipeline */}
      <div className="rounded-xl border border-slate-800/80 bg-[#0D1421] p-5">
        <div className="flex items-center gap-2 text-slate-200 mb-2 font-semibold text-sm">
          <FileText size={16} className="text-blue-400" />
          <span>Financial-Document Retrieval Pipeline (RAG Architecture)</span>
        </div>
        <p className="text-xs text-slate-300 leading-relaxed max-w-4xl mb-4">
          FinWiseAI retrieves lexical context for analysis claims. The current system does not call a generative model; retrieved text is not automatically factual support:
        </p>

        <div className="space-y-3 text-xs">
          <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-3 flex items-start gap-3">
            <span className="rounded bg-blue-500/10 px-2 py-0.5 font-mono text-[10px] font-bold text-blue-400 border border-blue-500/30 uppercase shrink-0">
              Passage Chunking
            </span>
            <div className="text-slate-300 leading-relaxed">
              Input text is split by paragraph into chunks targeting about 150 words with overlap, while retaining detected section headings, chunk indices, and persistent document/chunk IDs.
            </div>
          </div>

          <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-3 flex items-start gap-3">
            <span className="rounded bg-emerald-500/10 px-2 py-0.5 font-mono text-[10px] font-bold text-emerald-400 border border-emerald-500/30 uppercase shrink-0">
              BM25 Lexical Ranking
            </span>
            <div className="text-slate-300 leading-relaxed">
              Queries use a basic tokenizer and common-word stop list. Inverse document frequency and term-frequency saturation ($k_1=1.5, b=0.75$), plus a ticker match boost, rank stored passages. Relevance is lexical, not truth or contradiction detection.
            </div>
          </div>

          <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-3 flex items-start gap-3">
            <span className="rounded bg-purple-500/10 px-2 py-0.5 font-mono text-[10px] font-bold text-purple-400 border border-purple-500/30 uppercase shrink-0">
              Source Attribution
            </span>
            <div className="text-slate-300 leading-relaxed">
              Retrieved passages show title, period, BM25 relevance, excerpt, source metadata and link when supplied. Synthetic demo passages are visibly flagged. A context match does not verify or corroborate the associated claim.
            </div>
          </div>
        </div>
      </div>

      {/* SECTION E: Multi-Agent Aggregation Governance */}
      <div className="rounded-xl border border-slate-800/80 bg-[#0D1421] p-5">
        <div className="flex items-center gap-2 text-slate-200 mb-2 font-semibold text-sm">
          <Layers size={16} className="text-indigo-400" />
          <span>Multi-Agent Disagreement & Consensus Rules</span>
        </div>
        <p className="text-xs text-slate-300 leading-relaxed max-w-4xl mb-4">
          Three independent deterministic services (technical, fundamental and news) run concurrently and return structured assessments. These are not LLM agents. Synthesis consumes their returned status and evidence according to deterministic rules:
        </p>

        <div className="space-y-3 text-xs">
          <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-3 flex items-start gap-3">
            <span className="rounded bg-rose-500/10 px-2 py-0.5 font-mono text-[10px] font-bold text-rose-400 border border-rose-500/30 uppercase shrink-0">
              Rule 1
            </span>
            <div className="text-slate-300 leading-relaxed">
              <strong>Directional Conflict Priority:</strong> If any agent is <em>Bullish</em> while another is <em>Bearish</em>, the system declares an explicit Disagreement and sets the overall status to <strong>Neutral</strong>. FinWiseAI explicitly avoids averaging contradictory directional signals into an artificial bullish or bearish stance.
            </div>
          </div>

          <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-3 flex items-start gap-3">
            <span className="rounded bg-emerald-500/10 px-2 py-0.5 font-mono text-[10px] font-bold text-emerald-400 border border-emerald-500/30 uppercase shrink-0">
              Rule 2
            </span>
            <div className="text-slate-300 leading-relaxed">
              <strong>Multi-Agent Confirmation:</strong> If two or more directional agents agree without contradiction, that shared direction is returned as the overall status, accompanied by supporting evidence and remaining caveats.
            </div>
          </div>

          <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-3 flex items-start gap-3">
            <span className="rounded bg-orange-500/10 px-2 py-0.5 font-mono text-[10px] font-bold text-orange-400 border border-orange-500/30 uppercase shrink-0">
              Rule 3
            </span>
            <div className="text-slate-300 leading-relaxed">
              <strong>Insufficient Evidence Handling:</strong> If fewer than the required observations exist, or if all agents report insufficient data, the overall verdict strictly reflects <strong>Insufficient Data</strong>. Demo market samples are explicitly labeled synthetic and are not presented as live observations.
            </div>
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-slate-800/80 bg-[#0D1421] p-5">
        <div className="flex items-center gap-2 text-slate-200 mb-3 font-semibold text-sm">
          <Layers size={16} className="text-cyan-400" />
          <span>Session Metrics and Confidence Meaning</span>
        </div>
        <div className="space-y-2 text-xs text-slate-400 leading-relaxed">
          <p><strong>Analysis duration:</strong> elapsed milliseconds from analysis start through synthesis and optional profile interpretation, before persistence.</p>
          <p><strong>Agent duration:</strong> elapsed milliseconds for each technical, fundamental, and news task, including its failure path.</p>
          <p><strong>BM25 search duration:</strong> elapsed milliseconds for claim preparation and document searches.</p>
          <p><strong>Lexical evidence coverage:</strong> searched agent claims with at least one BM25 context match divided by searched claims. Null means retrieval did not complete or there were no claims; zero means a completed search found none. It is not factual support or predictive accuracy.</p>
          <p><strong>Confidence:</strong> heuristic rule concordance, available metric count, or headline volume/sentiment. It is not a calibrated probability.</p>
        </div>
      </div>

      {/* SECTION F: Forward Return Evaluation & Ethical Notice */}
      <div className="rounded-xl border border-slate-800/80 bg-[#0D1421] p-5">
        <div className="flex items-center gap-2 text-amber-400 mb-3 font-semibold text-sm">
          <ShieldAlert size={16} />
          <span>Historical Signal Evaluation & Ethical Notice</span>
        </div>

        <div className="space-y-3 text-xs text-slate-400 leading-relaxed">
          <p>
            • <strong>Forward Return Horizons:</strong> Directional signals are benchmarked against 30-calendar-day forward return windows ($&plusmn;1.5\%$ hurdle rate). The application currently records open windows as pending; it does not yet fetch exit observations or calculate outcomes for live signals.
          </p>
          <p>
            • <strong>No Fiduciary Relationship:</strong> FinWiseAI is an informational quantitative research workbench designed for investor education, hackathon demonstration, and transparent evidence exploration. It does not issue personalized financial recommendations, target prices, or warranties of profitability.
          </p>
        </div>
      </div>
    </div>
  );
}
