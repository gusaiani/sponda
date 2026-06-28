import { useQueries } from "@tanstack/react-query";
import { fetchQuote, type QuoteResult } from "./usePE10";
import { fetchMultiplesHistory } from "./useMultiplesHistory";
import { fetchFundamentals, type FundamentalsYear, type QuarterlyBalanceRatio } from "./useFundamentals";
import { deriveForYears } from "./deriveForYears";
import { buildChartData } from "../components/CompanyMetricsCard";
import { currencyCode } from "../utils/format";
import type { DataPoint } from "../components/MiniChart";

const COMPARISON_STALE_TIME = 30 * 60 * 1000;

interface CompanyBundle {
  quote: QuoteResult;
  prices: { date: string; adjustedClose: number }[];
  fundamentals: FundamentalsYear[];
  quarterlyRatios: QuarterlyBalanceRatio[];
}

export interface ComparisonCompany {
  ticker: string;
  name: string;
  /** Listing currency (the currency price and market-cap series are in). */
  currency: string;
  chartData: Record<string, DataPoint[]> | null;
  isLoading: boolean;
  isError: boolean;
}

/** Fetch the three series sources for a ticker in one shot so the comparison
 * bundle caches as a unit and survives `years` changes (rebuilt client-side). */
async function fetchComparisonBundle(ticker: string): Promise<CompanyBundle> {
  const [quote, multiples, fundamentals] = await Promise.all([
    fetchQuote(ticker),
    fetchMultiplesHistory(ticker),
    fetchFundamentals(ticker),
  ]);
  return {
    quote,
    prices: multiples.prices,
    fundamentals: fundamentals.years,
    quarterlyRatios: fundamentals.quarterlyRatios,
  };
}

/**
 * Build each comparison company's chart series with the same math the primary
 * company uses (`deriveForYears` → `buildChartData`), so an overlaid line is
 * computed identically to the line it is being compared against.
 */
export function useComparisonSeries(
  tickers: string[],
  years: number,
): ComparisonCompany[] {
  const results = useQueries({
    queries: tickers.map((ticker) => ({
      queryKey: ["compare-bundle", ticker],
      queryFn: () => fetchComparisonBundle(ticker),
      staleTime: COMPARISON_STALE_TIME,
      retry: false,
      enabled: !!ticker,
    })),
  });

  return tickers.map((ticker, index) => {
    const result = results[index];
    const bundle = result.data;
    const chartData = bundle
      ? buildChartData(
          deriveForYears(bundle.quote, years),
          bundle.prices,
          bundle.fundamentals,
          bundle.quarterlyRatios,
          years,
        )
      : null;
    return {
      ticker,
      name: bundle?.quote.name ?? ticker,
      currency: currencyCode(ticker),
      chartData,
      isLoading: result.isLoading,
      isError: result.isError,
    };
  });
}
