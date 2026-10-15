"use client";

import React, { useMemo, useState, useEffect } from "react";
import { useStockData } from "@/lib/stock-context";
import { SectionHeader, MetricCard, StatusBadge } from "@/components/shared/CommonComponents";
import { SentimentDistributionChart } from "@/components/charts/SentimentDistributionChart";
import { formatDate } from "@/lib/formatting";
import { searchDocuments } from "@/lib/api";
import { DocumentSearchResult } from "@/types";
import {
  Newspaper,
  ExternalLink,
  Compass,
  FileText,
  Search,
} from "lucide-react";

export default function NewsIntelligencePage() {
  const { symbol, intelligence } = useStockData();

  const newsAgent = intelligence?.assessments?.find((a) =>
    a.agent_name.includes("News"),
  );

  const rawArticles = intelligence?.news_articles;
  const allArticles = useMemo(() => rawArticles || [], [rawArticles]);
  const sentimentScore = intelligence?.news_sentiment_score ?? null;
  const citations = intelligence?.citations || [];

  // RAG Search State
  const initialRagQuery = `${symbol} revenue margin risk factors`;
  const [ragQueryState, setRagQueryState] = useState({
    symbol,
    query: initialRagQuery,
  });
  const ragQuery = ragQueryState.symbol === symbol
    ? ragQueryState.query
    : initialRagQuery;
  const [ragResults, setRagResults] = useState<DocumentSearchResult[]>([]);
  const [ragLoading, setRagLoading] = useState(false);
  const [ragError, setRagError] = useState(false);

  useEffect(() => {
    async function loadInitialRAG() {
      setRagLoading(true);
      setRagError(false);
      setRagResults([]);
      try {
        const res = await searchDocuments(initialRagQuery, symbol);
        setRagResults(res);
      } catch {
        setRagError(true);
      } finally {
        setRagLoading(false);
      }
    }
    void loadInitialRAG();
  }, [initialRagQuery, symbol]);

  const handleRAGSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ragQuery.trim()) return;
    setRagLoading(true);
    setRagError(false);
    setRagResults([]);
    try {
      const res = await searchDocuments(ragQuery.trim(), symbol);
      setRagResults(res);
    } catch {
      setRagError(true);
    } finally {
      setRagLoading(false);
    }
  };

  // Separate directly relevant company news from contextual sector news
  const { directArticles, contextualArticles } = useMemo(() => {
    const direct: typeof allArticles = [];
    const contextual: typeof allArticles = [];

    for (const art of allArticles) {
      if (art.relevance_score >= 0.7) {
        direct.push(art);
      } else {
        contextual.push(art);
      }
    }

    return { directArticles: direct, contextualArticles: contextual };
  }, [allArticles]);

  const negativeCount = allArticles.filter((a) => a.sentiment_label === "negative").length;

  return (
    <div className="space-y-6">
      <SectionHeader
        eyebrow="Narrative & Filing Engine"
        title={`News Sentiment & Financial-Document RAG — ${symbol}`}
        description="Sentiment scoring across available market feeds, with BM25 retrieval across filing-style passages clearly labeled as synthetic when they are demo data."
        rightAction={<StatusBadge status={newsAgent?.status || "neutral"} />}
      />

      {/* SECTION A: News Overview KPIs */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <MetricCard
          label="Processed Headlines"
          value={allArticles.length.toString()}
          subtext="Fetched & deduplicated"
        />
        <MetricCard
          label="Direct Company News"
          value={directArticles.length.toString()}
          tone="positive"
          subtext="Relevance &ge; 70%"
        />
        <MetricCard
          label="Contextual News"
          value={contextualArticles.length.toString()}
          subtext="Sector & macro roundups"
        />
        <MetricCard
          label="Sentiment Score"
          value={sentimentScore !== null ? sentimentScore.toFixed(2) : "—"}
          tone={
            sentimentScore !== null
              ? sentimentScore > 0.05
                ? "positive"
                : sentimentScore < -0.05
                ? "negative"
                : "warning"
              : "neutral"
          }
          subtext="Range [-1.0 to +1.0]"
        />
        <MetricCard
          label="Retrieved Citations"
          value={citations.length.toString()}
          tone="positive"
          subtext="BM25 context matches; not factual verification"
        />
        <MetricCard
          label="Negative Count"
          value={negativeCount.toString()}
          tone={negativeCount > 0 ? "negative" : "neutral"}
          subtext="Bearish keywords"
        />
      </div>

      {/* SECTION B: BM25 Document Context Explorer */}
      <div className="rounded-xl border border-slate-800/80 bg-[#111B2B] p-5 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-3">
          <div>
            <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-200 flex items-center gap-2">
              <FileText className="h-4 w-4 text-emerald-400" />
              Retrieved Document Context (BM25)
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              BM25 ranks lexical matches; it does not prove or contradict claims. Synthetic demo passages are labeled and are not official SEC filings.
            </p>
          </div>
          <span className="rounded bg-blue-500/10 px-2 py-0.5 text-xs font-semibold text-blue-400 border border-blue-500/20">
            BM25 Retrieval Engine Active
          </span>
        </div>

        {/* Live RAG Query Form */}
        <form onSubmit={handleRAGSearch} className="flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-500" />
            <input
              type="text"
              value={ragQuery}
              onChange={(e) => setRagQueryState({ symbol, query: e.target.value })}
              placeholder="Search indexed documents (e.g. cloud revenue, gross margin, antitrust risk)..."
              className="w-full rounded-lg border border-slate-700/80 bg-slate-900 py-2 pl-9 pr-3 text-xs text-slate-200 focus:border-emerald-500 focus:outline-none"
            />
          </div>
          <button
            type="submit"
            disabled={ragLoading}
            className="rounded-lg bg-emerald-500 px-4 py-2 text-xs font-semibold text-slate-950 transition hover:bg-emerald-400 disabled:opacity-50"
          >
            {ragLoading ? "Searching..." : "Retrieve Passages"}
          </button>
        </form>

        {/* Retrieved Results Grid */}
        {ragLoading ? (
          <div className="flex h-32 items-center justify-center">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-emerald-400 border-t-transparent" />
          </div>
        ) : ragError ? (
          <div role="status" className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-4 text-center text-xs text-amber-200">
            Document search is unavailable. No passages or citations are being shown for this query.
          </div>
        ) : ragResults.length > 0 ? (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {ragResults.map((r) => (
              <div
                key={r.chunk_id}
                className="rounded-lg border border-slate-800 bg-slate-900/60 p-3.5 space-y-2 text-xs"
              >
                <div className="flex items-center justify-between">
                  <span className="font-bold text-slate-200">{r.document_title}</span>
                  <span
                    className={`rounded px-1.5 py-0.5 text-[10px] font-bold uppercase ${
                      r.synthetic
                        ? "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                        : "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                    }`}
                  >
                    {r.synthetic ? "Synthetic Demo" : r.document_type}
                  </span>
                </div>

                <p className="border-l-2 border-emerald-500/60 pl-2.5 text-slate-300 text-xs leading-relaxed italic bg-slate-950/40 p-2 rounded">
                  &ldquo;{r.excerpt}&rdquo;
                </p>

                <div className="flex items-center justify-between text-[11px] text-slate-500 font-mono pt-1">
                  <span>Period: {r.reporting_period}</span>
                  <span className="text-blue-400 font-bold">BM25 relevance: {r.relevance_score.toFixed(3)}</span>
                  <span>Chunk: {r.chunk_id.slice(0, 8)}</span>
                  <span>{r.source_name}</span>
                  {r.source_url && (
                    <a
                      href={r.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-emerald-400 hover:underline flex items-center gap-1 font-sans"
                    >
                      Source Link <ExternalLink size={10} />
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="p-4 text-center text-xs text-slate-500 italic">
            No relevant document passages matched your query. No citation was fabricated. Try terms like &quot;revenue&quot;, &quot;margin&quot;, or &quot;risk&quot;.
          </div>
        )}
      </div>

      {/* SECTION C & D: Sentiment Visualization & Direct News */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <SentimentDistributionChart articles={allArticles} />

        <div className="flex flex-col justify-between rounded-xl border border-slate-800/80 bg-[#0D1421] p-5">
          <div>
            <div className="flex items-center gap-2 text-slate-200 mb-2 font-semibold text-sm">
              <Compass size={16} className="text-emerald-400" />
              <span>Sentiment Analysis Methodology</span>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed space-y-2">
              <span>
                FinWiseAI uses a multi-tiered narrative processor. Incoming articles are tagged by ticker relevance, filtered for noise and duplicates, and scored using financial lexicons.
              </span>
              <br /><br />
              <span>
                <strong>Direct News vs Contextual:</strong> Articles scoring &ge; 70% relevance focus specifically on company operations, whereas lower-scoring articles capture broad sector sentiment.
              </span>
            </p>
          </div>
          <div className="mt-4 pt-3 border-t border-slate-800/60 text-[11px] text-slate-500 font-mono">
            Observation timestamp: {formatDate(intelligence?.news_fetched_at_utc)}
          </div>
        </div>
      </div>

      {/* SECTION E: Direct Company News Headlines */}
      <div>
        <div className="mb-3 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
              <Newspaper size={16} className="text-emerald-400" />
              <span>Direct Company News ({directArticles.length})</span>
            </h3>
            <p className="text-xs text-slate-400">
              Headlines with direct operational and financial relevance to {symbol}
            </p>
          </div>
        </div>

        {directArticles.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {directArticles.map((art, idx) => (
              <div
                key={idx}
                className="rounded-xl border border-slate-800/80 bg-[#0D1421] p-4 text-xs space-y-2 flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between text-[10px] font-mono text-slate-500 mb-1">
                    <span>{art.publisher || "News provider"}</span>
                    <span
                      className={`font-semibold capitalize ${
                        art.sentiment_label === "positive"
                          ? "text-emerald-400"
                          : art.sentiment_label === "negative"
                          ? "text-rose-400"
                          : "text-slate-400"
                      }`}
                    >
                      {art.sentiment_label} ({art.sentiment_score > 0 ? "+" : ""}{art.sentiment_score.toFixed(2)})
                    </span>
                  </div>
                  <h4 className="font-semibold text-slate-200 line-clamp-2 leading-snug">
                    {art.title}
                  </h4>
                </div>

                <div className="flex items-center justify-between pt-2 border-t border-slate-800/60 text-[10px]">
                  <span className="text-slate-500 font-mono">
                    Relevance: {(art.relevance_score * 100).toFixed(0)}%
                  </span>
                  {art.link && (
                    <a
                      href={art.link}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="text-emerald-400 hover:text-emerald-300 flex items-center gap-1"
                    >
                      <span>Read</span>
                      <ExternalLink size={11} />
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="rounded-xl border border-slate-800 bg-[#0D1421] p-6 text-center text-xs text-slate-500 italic">
            No direct company news stories recorded for {symbol}.
          </div>
        )}
      </div>

      {/* SECTION F: Contextual Market News */}
      <div>
        <div className="mb-3 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
              <Newspaper size={16} className="text-indigo-400" />
              <span>Contextual Market & Sector News ({contextualArticles.length})</span>
            </h3>
            <p className="text-xs text-slate-400">
              Broad industry roundups and macro trends that mention {symbol} alongside other companies
            </p>
          </div>
        </div>

        {contextualArticles.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {contextualArticles.map((art, idx) => (
              <div
                key={idx}
                className="rounded-xl border border-slate-800/80 bg-[#0D1421] p-4 text-xs space-y-2 flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between text-[10px] font-mono text-slate-500 mb-1">
                    <span>{art.publisher || "News Feed"}</span>
                    <span className="capitalize text-slate-400">{art.sentiment_label}</span>
                  </div>
                  <h4 className="font-semibold text-slate-200 line-clamp-2 leading-snug">
                    {art.title}
                  </h4>
                </div>

                <div className="flex items-center justify-between pt-2 border-t border-slate-800/60 text-[10px]">
                  <span className="text-slate-500">Relevance: {(art.relevance_score * 100).toFixed(0)}%</span>
                  {art.link && (
                    <a
                      href={art.link}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="text-emerald-400 hover:text-emerald-300 flex items-center gap-1"
                    >
                      <span>Link</span>
                      <ExternalLink size={11} />
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="rounded-xl border border-slate-800 bg-[#0D1421] p-6 text-center text-xs text-slate-500 italic">
            No contextual market stories recorded.
          </div>
        )}
      </div>
    </div>
  );
}
