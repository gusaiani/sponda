import { useMemo } from "react";
import { useQueries } from "@tanstack/react-query";
import { type QuoteResult } from "./usePE10";
import { fetchFundamentals, type FundamentalsYear } from "./useFundamentals";
import { deriveForYears } from "./deriveForYears";
import { computeShillerPERatios } from "../components/FundamentalsTab";
import { useQuotesBatch } from "./useQuotesBatch";

export interface CompareEntry {
  ticker: string;
  data: QuoteResult | null;
  recent: FundamentalsYear | null;
  pe: number | null;
  pfcf: number | null;
  isLoading: boolean;
  error: Error | null;
}

const STALE_TIME = 30 * 60 * 1000;

interface UseCompareDataOptions {
  /** When false (home-page callers), skip the per-ticker fundamentals
   *  fan-out — `recent`, `pe`, and `pfcf` will be null. CompareTab and
   *  any caller that renders balance-sheet columns must keep this
   *  enabled (the default). */
  withFundamentals?: boolean;
}

export function useCompareData(
  tickers: string[],
  years: number,
  options: UseCompareDataOptions = {},
): CompareEntry[] {
  const { withFundamentals = true } = options;

  const batchQuery = useQuotesBatch(tickers);

  const fundamentalsQueries = useQueries({
    queries: tickers.map((t) => ({
      queryKey: ["fundamentals", t],
      queryFn: () => fetchFundamentals(t),
      enabled: withFundamentals && !!t,
      retry: false as const,
      staleTime: STALE_TIME,
    })),
  });

  return useMemo(
    () =>
      tickers.map((ticker, index) => {
        const upper = ticker.toUpperCase();
        const entry = batchQuery.data?.results?.[upper];
        const quote = entry?.quote ?? null;
        const data = quote ? deriveForYears(quote, years) : null;

        const fundamentals = fundamentalsQueries[index];
        const recentYear = fundamentals?.data?.years?.[0] ?? null;

        let pe: number | null = null;
        let pfcf: number | null = null;
        if (fundamentals?.data?.years && recentYear) {
          const ratios = computeShillerPERatios(fundamentals.data.years, years).get(
            recentYear.year,
          );
          pe = ratios?.pe ?? null;
          pfcf = ratios?.pfcf ?? null;
        }

        const isLoading =
          batchQuery.isLoading || (withFundamentals && (fundamentals?.isLoading ?? false));
        const errorMessage = entry?.error;
        const error: Error | null =
          (batchQuery.error as Error | null) ??
          (fundamentals?.error as Error | null) ??
          (errorMessage ? new Error(errorMessage) : null);

        return {
          ticker,
          data,
          recent: recentYear,
          pe,
          pfcf,
          isLoading,
          error,
        };
      }),
    [tickers, years, batchQuery.data, batchQuery.isLoading, batchQuery.error, fundamentalsQueries, withFundamentals],
  );
}
