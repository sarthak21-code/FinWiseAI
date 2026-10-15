export type AgentStatus =
  | "bullish"
  | "bearish"
  | "neutral"
  | "insufficient_data"
  | "unavailable"
  | string;

export type GroundedCitation = {
  citation_id: string;
  claim: string;
  claim_type: "context" | "supported" | "limitation" | "contradictory" | string;
  document_id: string;
  chunk_id: string;
  document_title: string;
  issuer: string;
  ticker: string;
  reporting_period: string;
  excerpt: string;
  relevance_score: number;
  synthetic: boolean;
  source_name?: string;
  source_url?: string | null;
};

export type StructuredSignal = {
  signal_id: string;
  symbol: string;
  dimension: "price_momentum" | "volume_anomaly" | "news_sentiment" | "fundamental_health" | "synthesis" | string;
  classification: "bullish" | "bearish" | "neutral" | "insufficient_data" | "unavailable" | string;
  confidence: number;
  confidence_method: string;
  observed_at: string;
  source: string;
  evidence: string[];
  limitations: string[];
  data_status: string;
  metrics: Record<string, number | string | boolean | null>;
};

export type ReasoningStep = {
  step_number: number;
  title: string;
  description: string;
  outcome: string;
  metadata?: Record<string, number | string | boolean | null>;
};

export type PersonalizedAnalysis = {
  profile_id: string;
  profile_name: string;
  risk_tolerance: number;
  suitability_rating: string;
  risk_emphasis: string;
  portfolio_impact_analysis: string;
  concentration_warning?: string | null;
  suggested_investor_questions: string[];
  underlying_market_facts_unaltered: boolean;
};

export type AgentAssessment = {
  agent_name: string;
  status: AgentStatus;
  summary: string;
  evidence: string[];
  limitations: string[];
  source: string;
  is_demo: boolean;
  agent_id?: string | null;
  latency_ms?: number;
  confidence?: number;
  confidence_method?: string | null;
  citations?: GroundedCitation[];
};

export type AgentDisagreement = {
  agents: string[];
  conflict: string;
  evidence: string[];
  significance: "low" | "medium" | "high" | string;
};

export type NewsArticle = {
  id?: string | null;
  title: string;
  publisher?: string | null;
  link?: string | null;
  published_at_utc: string;
  sentiment_score: number;
  sentiment_label: "positive" | "negative" | "neutral" | string;
  relevance_score: number;
  related_tickers: string[];
};

export type IntelligenceResponse = {
  symbol: string;
  generated_at_utc: string;
  overall_status: AgentStatus;
  analysis_completeness: "complete" | "partial";
  assessments: AgentAssessment[];
  disagreements: AgentDisagreement[];
  data_warnings: string[];
  analysis_note: string;
  news_sentiment_score: number | null;
  news_fetched_at_utc: string | null;
  news_articles: NewsArticle[];
  session_id?: string | null;
  total_latency_ms?: number;
  rag_latency_ms?: number;
  evidence_claims_count?: number;
  evidence_cited_claims_count?: number;
  evidence_coverage_percent?: number | null;
  signals?: StructuredSignal[];
  citations?: GroundedCitation[];
  reasoning_trace?: ReasoningStep[];
  personalized_interpretation?: PersonalizedAnalysis | null;
  profile_id?: string | null;
};

export type MarketQuote = {
  symbol?: string;
  price?: number | string | null;
  close?: number | string | null;
  latest_close?: number | string | null;
  current_price?: number | string | null;
  change?: number | string | null;
  change_percent?: number | string | null;
  open?: number | string | null;
  high?: number | string | null;
  low?: number | string | null;
  previous_close?: number | string | null;
  volume?: number | string | null;
  currency?: string | null;
  latest_trading_day?: string | null;
  fetched_at_utc?: string | null;
  date?: string | null;
  source?: string | null;
  is_demo?: boolean;
  data_note?: string | null;
  note?: string | null;
};

export type HistoricalBar = {
  trading_day: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number;
  volume: number | null;
};

export type HistoricalPriceResponse = {
  symbol: string;
  bars: HistoricalBar[];
  source: string;
  fetched_at_utc: string;
  data_note: string;
};

export type TechnicalMetrics = {
  symbol: string;
  latest_close: number;
  latest_trading_day: string;
  calculated_at_utc: string;
  sma_20: number | null;
  sma_50: number | null;
  rsi_14: number | null;
  momentum_20d_percent: number | null;
  daily_volatility_percent: number | null;
  technical_bias: string;
  evidence: string[];
  source: string;
  is_demo: boolean;
  data_note: string;
};

export type FundamentalMetrics = {
  symbol: string;
  company_name: string | null;
  currency: string | null;
  fiscal_year: string | null;
  fiscal_period: string | null;
  revenue: number | null;
  revenue_growth_percent: number | null;
  net_income: number | null;
  net_margin_percent: number | null;
  return_on_equity_percent: number | null;
  debt_to_equity: number | null;
  current_ratio: number | null;
  pe_ratio: number | null;
  eps: number | null;
  source: string;
  fetched_at_utc: string;
  is_demo: boolean;
  data_warnings: string[];
};

export type InvestorProfile = {
  id: string;
  name: string;
  risk_tolerance: number;
  investment_horizon_months: number;
  max_single_asset_allocation: number;
  investment_objective?: string;
  created_at: string;
};

export type PortfolioHolding = {
  id: string;
  profile_id: string;
  symbol: string;
  shares: number;
  weight: number;
  cost_basis?: number | null;
  asset_category: string;
  is_watchlist: boolean;
  created_at: string;
};

export type PortfolioRiskMetrics = {
  profile_id: string;
  profile_name: string;
  risk_tolerance: number;
  investment_horizon_months: number;
  investment_objective: string;
  total_holdings_count: number;
  hhi_score: number;
  concentration_level: string;
  largest_position_symbol?: string | null;
  largest_position_weight: number;
  max_allocation_limit: number;
  allocation_breached: boolean;
  warnings: string[];
  holdings: PortfolioHolding[];
  watchlist: PortfolioHolding[];
};

export type ProfileComparisonResponse = {
  symbol: string;
  market_facts_unaltered: boolean;
  overall_status: AgentStatus;
  profile_a: PersonalizedAnalysis;
  profile_b: PersonalizedAnalysis;
  comparison_summary: string;
};

export type EvaluationMetrics = {
  total_sessions: number;
  average_total_latency_ms: number;
  average_rag_latency_ms: number;
  agent_latencies: Record<string, number>;
  total_signals_evaluated: number;
  synthetic_signals_evaluated: number;
  completed_windows_count: number;
  pending_windows_count: number;
  unavailable_windows_count: number;
  excluded_windows_count: number;
  synthetic_completed_windows_count: number;
  synthetic_pending_windows_count: number;
  accuracy_rate_percent: number;
  accurate_signals_count: number;
  inaccurate_signals_count: number;
  inconclusive_signals_count: number;
  evaluation_history: Array<{
    id: string;
    symbol: string;
    dimension: string;
    classification: string;
    entry_price: number;
    exit_price?: number | null;
    horizon_days: number;
    signal_date: string;
    target_date: string;
    actual_return_percent?: number | null;
    outcome: string;
    status: "pending" | "unavailable" | "evaluated" | "excluded";
    status_detail?: string | null;
    is_synthetic: boolean;
  }>;
  recent_sessions: Array<{
    id: string;
    symbol: string;
    status: string;
    overall_classification: string;
    analysis_completeness: "complete" | "partial" | "unknown";
    total_latency_ms: number;
    rag_latency_ms: number;
    created_at: string;
    evaluation_status_counts: {
      evaluated: number;
      pending: number;
      unavailable: number;
      excluded: number;
    };
  }>;
  last_updated_at: string;
};

export type DocumentSearchResult = {
  document_id: string;
  chunk_id: string;
  document_title: string;
  issuer: string;
  ticker: string;
  document_type: string;
  reporting_period: string;
  published_at: string;
  source_name: string;
  source_url?: string | null;
  relevance_score: number;
  excerpt: string;
  synthetic: boolean;
};

export type StockBundle = {
  symbol: string;
  quote: MarketQuote | null;
  history: HistoricalPriceResponse | null;
  technical: TechnicalMetrics | null;
  fundamental: FundamentalMetrics | null;
  intelligence: IntelligenceResponse | null;
  loading: boolean;
  error: string | null;
  updatedAt: string | null;
};
