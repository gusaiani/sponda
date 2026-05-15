import { dehydrate, HydrationBoundary, QueryClient } from "@tanstack/react-query";

import { batchQueryKey } from "../../hooks/useQuotesBatch";
import { isSupportedLocale } from "../../lib/i18n-config";
import { serverFetchJSON } from "../../lib/serverApi";
import type { Locale } from "../../i18n/types";

import { HomePageInteractive } from "./HomePageInteractive";

interface FavoriteEntry {
  id: number;
  ticker: string;
  created_at: string;
}

interface SavedListEntry {
  id: number;
  name: string;
  tickers: string[];
}

// Force-dynamic: the home page is per-user (favorites + saved lists),
// so static caching cannot be used. Streaming SSR still beats a blank
// page + hydration spinner because the user sees real cards in the
// first byte instead of after ~30 client fetches.
export const dynamic = "force-dynamic";

export default async function HomePage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale: rawLocale } = await params;
  const locale: Locale = isSupportedLocale(rawLocale) ? rawLocale : "en";

  const queryClient = new QueryClient();

  // Prefetch favorites + saved lists. Failures are non-fatal: we fall
  // back to the existing client-side fetch path on hydration.
  const [favorites, savedLists] = await Promise.all([
    serverFetchJSON<FavoriteEntry[]>(
      "/api/auth/favorites/",
      undefined,
      [],
    ),
    serverFetchJSON<SavedListEntry[]>(
      "/api/auth/lists/",
      undefined,
      [],
    ),
  ]);

  queryClient.setQueryData(["favorites"], favorites);
  queryClient.setQueryData(["saved-lists"], savedLists);

  // Build the union of tickers worth prefetching. Cap at the batch
  // endpoint's max so we never send a request that would 400.
  const tickerSet = new Set<string>();
  for (const favorite of favorites) {
    if (favorite.ticker) tickerSet.add(favorite.ticker.toUpperCase());
  }
  for (const list of savedLists) {
    if (Array.isArray(list.tickers)) {
      for (const ticker of list.tickers) {
        if (typeof ticker === "string") {
          tickerSet.add(ticker.toUpperCase());
        }
      }
    }
  }
  const tickers = Array.from(tickerSet).slice(0, 100);

  if (tickers.length > 0) {
    const batchPayload = await serverFetchJSON<{
      results: Record<string, { quote?: unknown; error?: string }>;
    }>(
      "/api/quotes/batch/",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tickers }),
      },
      { results: {} },
    );

    queryClient.setQueryData(batchQueryKey(tickers), batchPayload);

    // Seed individual quote keys so per-ticker callers (e.g. drill-down
    // pages opened from the home grid) read from cache rather than
    // round-tripping again.
    for (const ticker of tickers) {
      const entry = batchPayload.results[ticker];
      if (entry?.quote) {
        queryClient.setQueryData(["pe10", ticker], entry.quote);
      }
    }
  }

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <HomePageInteractive locale={locale} />
    </HydrationBoundary>
  );
}
