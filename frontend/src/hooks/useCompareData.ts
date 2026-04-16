import { useMemo } from "react";
import { useQueries } from "@tanstack/react-query";
import { fetchQuote, type QuoteResult } from "./usePE10";
import { fetchFundamentals, type FundamentalsYear } from "./useFundamentals";
import { deriveForYears } from "./deriveForYears";
import { computeShillerPERatios } from "../components/FundamentalsTab";

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

export function useCompareData(tickers: string[], years: number): CompareEntry[] {
  const quoteQueries = useQueries({
    queries: tickers.map((t) => ({
      queryKey: ["pe10", t],
      queryFn: () => fetchQuote(t),
      enabled: !!t,
      retry: false as const,
      staleTime: STALE_TIME,
    })),
  });

  const fundamentalsQueries = useQueries({
    queries: tickers.map((t) => ({
      queryKey: ["fundamentals", t],
      queryFn: () => fetchFundamentals(t),
      enabled: !!t,
      retry: false as const,
      staleTime: STALE_TIME,
    })),
  });

  return useMemo(
    () =>
      tickers.map((ticker, i) => {
        const quote = quoteQueries[i];
        const fundamentals = fundamentalsQueries[i];

        const data = quote.data ? deriveForYears(quote.data, years) : null;
        const recentYear = fundamentals.data?.years?.[0] ?? null;

        let pe: number | null = null;
        let pfcf: number | null = null;
        if (fundamentals.data?.years && recentYear) {
          const ratios = computeShillerPERatios(fundamentals.data.years, years).get(recentYear.year);
          pe = ratios?.pe ?? null;
          pfcf = ratios?.pfcf ?? null;
        }

        return {
          ticker,
          data,
          recent: recentYear,
          pe,
          pfcf,
          isLoading: quote.isLoading || fundamentals.isLoading,
          error: (quote.error ?? fundamentals.error) as Error | null,
        };
      }),
    [tickers, quoteQueries, fundamentalsQueries, years],
  );
}
