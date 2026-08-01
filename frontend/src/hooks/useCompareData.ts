import { useMemo } from "react";
import { useQueries } from "@tanstack/react-query";
import { type QuoteResult } from "./usePE10";
import { fetchFundamentals, type FundamentalsYear } from "./useFundamentals";
import { deriveForYears, effectiveYearsForCompany } from "./deriveForYears";
import { useQuotesBatch } from "./useQuotesBatch";

export interface CompareEntry {
  ticker: string;
  data: QuoteResult | null;
  recent: FundamentalsYear | null;
  /** Window-aware trailing-periods P/L — identical to the Indicadores
   *  tab's value for the same window. Null when the company lacks
   *  enough filings for the window. */
  pe: number | null;
  /** Same for P/FCL. */
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
  /** When true, cap each company's derivation window to its own
   *  `maxYearsAvailable`. The homepage uses this so a short-history
   *  ticker (e.g. Duolingo) still surfaces its computable indicators
   *  and earns a Learn grade badge when the slider is set higher than
   *  its data window. CompareTab keeps the default (strict apples-to-
   *  apples comparison across the same window). */
  autoCapPerCompany?: boolean;
}

export function useCompareData(
  tickers: string[],
  years: number,
  options: UseCompareDataOptions = {},
): CompareEntry[] {
  const { withFundamentals = true, autoCapPerCompany = false } = options;

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
        const yearsForQuote = quote && autoCapPerCompany
          ? effectiveYearsForCompany(years, quote.maxYearsAvailable)
          : years;
        const data = quote ? deriveForYears(quote, yearsForQuote) : null;

        const fundamentals = fundamentalsQueries[index];
        const recentYear = fundamentals?.data?.years?.[0] ?? null;

        // P/L and P/FCL come from the same window-aware derivation the
        // Indicadores tab uses, so the two views can never disagree. A
        // partial current year is weighted by its actual filings (the
        // window trails into older periods), never counted as a full year.
        const pe = data?.pe10 ?? null;
        const pfcf = data?.pfcf10 ?? null;

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
    [tickers, years, batchQuery.data, batchQuery.isLoading, batchQuery.error, fundamentalsQueries, withFundamentals, autoCapPerCompany],
  );
}
