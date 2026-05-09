import { useQuery, useQueryClient } from "@tanstack/react-query";
import * as Sentry from "@sentry/nextjs";

import { type QuoteResult } from "./usePE10";

const STALE_TIME = 30 * 60 * 1000;

interface BatchEntry {
  quote?: QuoteResult;
  error?: string;
}

interface BatchResponse {
  results: Record<string, BatchEntry>;
}

/** Fetches many tickers in one request. Server fans out internally. */
export async function fetchQuotesBatch(tickers: string[]): Promise<BatchResponse> {
  const response = await fetch("/api/quotes/batch/", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tickers }),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Batch request failed (${response.status})`);
  }

  return response.json();
}

/** Sorted, normalized cache key — order- and case-independent. */
export function batchQueryKey(tickers: string[]): readonly unknown[] {
  return ["quotes-batch", [...new Set(tickers.map((t) => t.toUpperCase()))].sort()];
}

/**
 * Single-request alternative to per-ticker fetchQuote(). Replaces the
 * home page's ~30-way fanout with one round-trip and seeds individual
 * react-query keys so other components (drill-downs, cards) keep
 * benefitting from the same cache.
 */
export function useQuotesBatch(tickers: string[]) {
  const queryClient = useQueryClient();
  const normalized = [...new Set(tickers.map((t) => t.toUpperCase()))];

  return useQuery({
    queryKey: batchQueryKey(normalized),
    queryFn: async () => {
      return Sentry.startSpan(
        {
          name: "homepage.quotes-batch",
          op: "fetch.batch",
          attributes: { "tickers.count": normalized.length },
        },
        async () => {
          const response = await fetchQuotesBatch(normalized);
          for (const ticker of normalized) {
            const entry = response.results[ticker];
            if (entry?.quote) {
              queryClient.setQueryData(["pe10", ticker], entry.quote);
            }
          }
          return response;
        },
      );
    },
    enabled: normalized.length > 0,
    retry: false,
    staleTime: STALE_TIME,
  });
}
