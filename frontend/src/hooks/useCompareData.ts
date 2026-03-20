import { useMemo } from "react";
import { useQueries } from "@tanstack/react-query";
import { fetchQuote, type QuoteResult } from "./usePE10";
import { deriveForYears } from "./deriveForYears";

export interface CompareEntry {
  ticker: string;
  data: QuoteResult | null;
  isLoading: boolean;
  error: Error | null;
}

export function useCompareData(tickers: string[], years: number): CompareEntry[] {
  const results = useQueries({
    queries: tickers.map((t) => ({
      queryKey: ["pe10", t],
      queryFn: () => fetchQuote(t),
      enabled: !!t,
      retry: false as const,
      staleTime: 5 * 60 * 1000,
    })),
  });

  return useMemo(
    () =>
      results.map((r, i) => ({
        ticker: tickers[i],
        data: r.data ? deriveForYears(r.data, years) : null,
        isLoading: r.isLoading,
        error: r.error as Error | null,
      })),
    [results, tickers, years],
  );
}
