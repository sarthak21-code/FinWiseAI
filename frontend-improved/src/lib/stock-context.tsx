"use client";

import React, { createContext, useContext, useEffect, useState, useCallback, Suspense } from "react";
import { useSearchParams, useRouter, usePathname } from "next/navigation";
import {
  StockBundle,
  MarketQuote,
  HistoricalPriceResponse,
  TechnicalMetrics,
  FundamentalMetrics,
  IntelligenceResponse,
  InvestorProfile,
} from "@/types";
import {
  fetchFundamentalMetrics,
  fetchHistoricalPrices,
  fetchIntelligence,
  fetchMarketQuote,
  fetchProfiles,
  createInvestorProfile,
  fetchTechnicalAnalysis,
} from "@/lib/api";

type StockContextType = StockBundle & {
  setSelectedSymbol: (symbol: string) => void;
  refreshData: () => void;
  selectedProfileId: string;
  setSelectedProfileId: (id: string) => void;
  profiles: InvestorProfile[];
  profileSetupError: string | null;
};

const StockContext = createContext<StockContextType | undefined>(undefined);

const DEFAULT_SYMBOL = "AAPL";
function StockDataProviderInner({ children }: { children: React.ReactNode }) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const urlTicker = searchParams.get("ticker");
  const [symbol, setSymbol] = useState<string>(
    urlTicker ? urlTicker.toUpperCase().trim() : DEFAULT_SYMBOL,
  );

  const [selectedProfileId, setSelectedProfileId] = useState<string>("");
  const [profiles, setProfiles] = useState<InvestorProfile[]>([]);
  const [profilesReady, setProfilesReady] = useState(false);
  const [profileSetupError, setProfileSetupError] = useState<string | null>(null);

  const [quote, setQuote] = useState<MarketQuote | null>(null);
  const [history, setHistory] = useState<HistoricalPriceResponse | null>(null);
  const [technical, setTechnical] = useState<TechnicalMetrics | null>(null);
  const [fundamental, setFundamental] = useState<FundamentalMetrics | null>(null);
  const [intelligence, setIntelligence] = useState<IntelligenceResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);

  // Load profiles on mount
  useEffect(() => {
    if (pathname === "/login") return;
    async function initProfiles() {
      try {
        let loaded = await fetchProfiles();
        if (!loaded || loaded.length === 0) {
          const created = await createInvestorProfile({
            name: "My Investor Profile",
            risk_tolerance: 3,
            investment_horizon_months: 12,
            max_single_asset_allocation: 0.2,
            investment_objective: "Capital Growth",
          });
          loaded = created ? [created] : [];
          if (loaded.length === 0) {
            setProfileSetupError(
              "Your profile could not be initialized. Please refresh after signing in again.",
            );
          }
        }
        setProfiles(loaded);
        setSelectedProfileId(loaded[0]?.id ?? "");
      } catch {
        setProfileSetupError(
          "Your profile could not be initialized. Please refresh after signing in again.",
        );
        setProfiles([]);
      } finally {
        setProfilesReady(true);
      }
    }
    void initProfiles();
  }, [pathname]);

  const loadStockData = useCallback(async (targetSymbol: string, profileId?: string) => {
    const cleanSym = targetSymbol.trim().toUpperCase();
    if (!/^[A-Z0-9.^=-]{1,24}$/.test(cleanSym)) {
      setSymbol(cleanSym);
      setQuote(null);
      setHistory(null);
      setTechnical(null);
      setFundamental(null);
      setIntelligence(null);
      setError("Please enter a valid ticker symbol (e.g. AAPL, MSFT, NVDA).");
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    const activeProfile = profileId || selectedProfileId;

    try {
      const [intelResult, quoteRes, histRes, techRes, fundRes] = await Promise.all([
        fetchIntelligence(cleanSym, activeProfile).catch((e) => e as Error),
        fetchMarketQuote(cleanSym),
        fetchHistoricalPrices(cleanSym),
        fetchTechnicalAnalysis(cleanSym),
        fetchFundamentalMetrics(cleanSym),
      ]);

      if (intelResult instanceof Error) {
        setError(intelResult.message);
        setIntelligence(null);
      } else {
        setIntelligence(intelResult);
      }

      setQuote(quoteRes);
      setHistory(histRes);
      setTechnical(techRes);
      setFundamental(fundRes);
      setSymbol(cleanSym);
      setUpdatedAt(new Date().toISOString());
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Unable to load market data.";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [selectedProfileId]);

  useEffect(() => {
    if (pathname === "/login" || !profilesReady || !selectedProfileId) return;
    const target = urlTicker ? urlTicker.toUpperCase().trim() : DEFAULT_SYMBOL;
    void Promise.resolve().then(() => loadStockData(target, selectedProfileId));
  }, [loadStockData, urlTicker, selectedProfileId, profilesReady, pathname]);

  const setSelectedSymbol = useCallback(
    (newSymbol: string) => {
      const clean = newSymbol.trim().toUpperCase();
      if (clean === symbol) return;

      const params = new URLSearchParams(searchParams.toString());
      params.set("ticker", clean);
      router.push(`${pathname}?${params.toString()}`);
    },
    [pathname, router, searchParams, symbol],
  );

  const refreshData = useCallback(() => {
    void loadStockData(symbol, selectedProfileId);
  }, [loadStockData, symbol, selectedProfileId]);

  return (
    <StockContext.Provider
      value={{
        symbol,
        quote,
        history,
        technical,
        fundamental,
        intelligence,
        loading,
        error,
        updatedAt,
        setSelectedSymbol,
        refreshData,
        selectedProfileId,
        setSelectedProfileId,
        profiles,
        profileSetupError,
      }}
    >
      {children}
    </StockContext.Provider>
  );
}

export function StockDataProvider({ children }: { children: React.ReactNode }) {
  return (
    <Suspense
      fallback={
        <div className="flex h-screen w-full items-center justify-center bg-[#080D16] text-slate-400">
          <div className="flex items-center gap-3">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-emerald-400 border-t-transparent" />
            <span>Initializing FinWiseAI...</span>
          </div>
        </div>
      }
    >
      <StockDataProviderInner>{children}</StockDataProviderInner>
    </Suspense>
  );
}

export function useStockData(): StockContextType {
  const context = useContext(StockContext);
  if (!context) {
    throw new Error("useStockData must be used within a StockDataProvider");
  }
  return context;
}
