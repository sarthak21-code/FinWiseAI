import {
  DocumentSearchResult,
  EvaluationMetrics,
  FundamentalMetrics,
  HistoricalPriceResponse,
  IntelligenceResponse,
  InvestorProfile,
  MarketQuote,
  PortfolioRiskMetrics,
  ProfileComparisonResponse,
  TechnicalMetrics,
} from "@/types";

export interface DocumentChunkDetail {
  chunk_id: string;
  chunk_index: number;
  section: string;
  text: string;
  token_count: number;
}

export interface DocumentDetail {
  id: string;
  issuer: string;
  ticker: string;
  title: string;
  document_type: string;
  reporting_period: string;
  published_at: string;
  source_name: string;
  source_url: string | null;
  synthetic: boolean;
  raw_content: string;
  chunks: DocumentChunkDetail[];
}

export interface DemoSeedResult {
  status: string;
  documents_seeded: number;
  profiles_seeded: number;
  historical_evaluations_seeded: number;
  message: string;
}

export function cleanErrorMessage(rawMessage: string): string {
  if (!rawMessage) return "An unexpected error occurred.";

  const text = String(rawMessage);

  if (
    text.includes("Alpha Vantage") &&
    (text.includes("standard API rate limit") ||
      text.includes("premium membership") ||
      text.includes("thank you for using"))
  ) {
    return "Market data provider rate limit reached. FinWiseAI uses the secondary provider fallback where available.";
  }

  if (text.includes("Cannot connect to the FinWiseAI analysis service")) {
    return "Cannot connect to the FinWiseAI analysis service. Please check that the backend is running on port 8000.";
  }

  if (text.includes("503") || text.includes("MarketDataUnavailable")) {
    return "Market data provider is currently unavailable for this symbol. No synthetic data was substituted.";
  }

  if (text.includes("Invalid ticker") || text.includes("422")) {
    return "Invalid ticker format. Please enter a valid stock symbol (e.g. AAPL, MSFT, NVDA).";
  }

  return text.slice(0, 160);
}

export async function fetchMarketQuote(symbol: string): Promise<MarketQuote | null> {
  const encoded = encodeURIComponent(symbol);
  const response = await fetch(`/api/backend/api/v1/market/quote/${encoded}`, {
    cache: "no-store",
  }).catch(() => null);

  if (!response || !response.ok) return null;
  return response.json().catch(() => null);
}

export async function fetchHistoricalPrices(symbol: string): Promise<HistoricalPriceResponse | null> {
  const encoded = encodeURIComponent(symbol);
  const response = await fetch(`/api/backend/api/v1/market/history/${encoded}`, {
    cache: "no-store",
  }).catch(() => null);

  if (!response || !response.ok) return null;
  return response.json().catch(() => null);
}

export async function fetchTechnicalAnalysis(symbol: string): Promise<TechnicalMetrics | null> {
  const encoded = encodeURIComponent(symbol);
  const response = await fetch(`/api/backend/api/v1/market/technical/${encoded}`, {
    cache: "no-store",
  }).catch(() => null);

  if (!response || !response.ok) return null;
  return response.json().catch(() => null);
}

export async function fetchFundamentalMetrics(symbol: string): Promise<FundamentalMetrics | null> {
  const encoded = encodeURIComponent(symbol);
  const response = await fetch(`/api/backend/api/v1/market/fundamental/${encoded}`, {
    cache: "no-store",
  }).catch(() => null);

  if (!response || !response.ok) return null;
  return response.json().catch(() => null);
}

export async function fetchIntelligence(
  symbol: string,
  profileId?: string | null,
): Promise<IntelligenceResponse> {
  const encoded = encodeURIComponent(symbol);
  let url = `/api/backend/api/v1/intelligence/analyze/${encoded}`;
  if (profileId) {
    url += `?profile_id=${encodeURIComponent(profileId)}`;
  }

  const response = await fetch(url, {
    cache: "no-store",
  });

  const payload = await response.json().catch(() => null);

  if (!response.ok) {
    const rawDetail = payload?.detail ?? `Intelligence request failed (${response.status}).`;
    throw new Error(cleanErrorMessage(String(rawDetail)));
  }

  return payload as IntelligenceResponse;
}

export async function fetchProfiles(): Promise<InvestorProfile[]> {
  const response = await fetch("/api/backend/api/v1/profiles", {
    cache: "no-store",
  }).catch(() => null);

  if (!response || !response.ok) return [];
  return response.json().catch(() => []);
}

export async function createInvestorProfile(
  profile: Pick<InvestorProfile, "name" | "risk_tolerance" | "investment_horizon_months" | "max_single_asset_allocation" | "investment_objective">,
): Promise<InvestorProfile | null> {
  const response = await fetch("/api/backend/api/v1/profiles", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(profile),
    cache: "no-store",
  }).catch(() => null);
  if (!response || !response.ok) return null;
  return response.json().catch(() => null);
}

export async function fetchProfilePortfolio(profileId: string): Promise<PortfolioRiskMetrics | null> {
  const encoded = encodeURIComponent(profileId);
  const response = await fetch(`/api/backend/api/v1/profiles/${encoded}/portfolio`, {
    cache: "no-store",
  }).catch(() => null);

  if (!response || !response.ok) return null;
  return response.json().catch(() => null);
}

export async function compareProfiles(
  symbol: string,
  profileAId: string,
  profileBId: string,
): Promise<ProfileComparisonResponse | null> {
  const response = await fetch("/api/backend/api/v1/intelligence/compare-profiles", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      symbol,
      profile_a_id: profileAId,
      profile_b_id: profileBId,
    }),
    cache: "no-store",
  }).catch(() => null);

  if (!response || !response.ok) return null;
  return response.json().catch(() => null);
}

export async function fetchEvaluationMetrics(): Promise<EvaluationMetrics | null> {
  const response = await fetch("/api/backend/api/v1/intelligence/evaluation", {
    cache: "no-store",
  }).catch(() => null);

  if (!response || !response.ok) return null;
  return response.json().catch(() => null);
}

export async function searchDocuments(
  query: string,
  symbol?: string,
): Promise<DocumentSearchResult[]> {
  let url = `/api/backend/api/v1/documents/search?q=${encodeURIComponent(query)}`;
  if (symbol) {
    url += `&symbol=${encodeURIComponent(symbol)}`;
  }

  const response = await fetch(url, {
    cache: "no-store",
  }).catch(() => null);

  if (!response || !response.ok) return [];
  return response.json().catch(() => []);
}

export async function fetchDocumentDetail(docId: string): Promise<DocumentDetail | null> {
  const encoded = encodeURIComponent(docId);
  const response = await fetch(`/api/backend/api/v1/documents/${encoded}`, {
    cache: "no-store",
  }).catch(() => null);

  if (!response || !response.ok) return null;
  return response.json().catch(() => null);
}

export async function seedDemoEnvironment(): Promise<DemoSeedResult | null> {
  const response = await fetch("/api/backend/api/v1/demo/seed", {
    method: "POST",
    cache: "no-store",
  }).catch(() => null);

  if (!response || !response.ok) return null;
  return response.json().catch(() => null);
}
