import { useEffect, useRef, useState } from "react";
import { useQueryClient, type QueryClient } from "@tanstack/react-query";

export const STATUS_POLL_INTERVAL_MS = 1500;
// 20 polls at 1.5s is 30s, many times the 1 to 3 seconds a refresh takes.
// Past that the background worker is presumably down, so stop asking.
export const MAX_STATUS_POLLS = 20;

const REFRESHED_QUERY_KEY_PREFIXES = ["pe10", "fundamentals", "multiples-history"];

interface PollingCycle {
  isCancelled: boolean;
  timerId: ReturnType<typeof setTimeout> | null;
}

/**
 * Asks the server whether the statement refresh is still running. A failed
 * poll answers "still pending": the refresh is not known to be over, and
 * the attempt limit bounds how long we keep asking.
 */
async function fetchIsRefreshPending(ticker: string): Promise<boolean> {
  try {
    const response = await fetch(`/api/quote/${ticker}/refresh-status/`, {
      cache: "no-store",
    });
    if (!response.ok) return true;
    const status: { refreshPending?: boolean } = await response.json();
    return status.refreshPending !== false;
  } catch {
    return true;
  }
}

function cancelCycle(cycle: PollingCycle) {
  cycle.isCancelled = true;
  if (cycle.timerId !== null) clearTimeout(cycle.timerId);
}

function refetchRefreshedPayloads(queryClient: QueryClient, ticker: string) {
  return Promise.all(
    REFRESHED_QUERY_KEY_PREFIXES.map((keyPrefix) =>
      queryClient.invalidateQueries({ queryKey: [keyPrefix, ticker] }),
    ),
  );
}

/**
 * Follows a background statement refresh to its end.
 *
 * The server answers with stored statements while it refetches them. When a
 * payload says so (`isRefreshPending`), this polls the status endpoint and,
 * once the refresh is done, invalidates the three payloads so they refetch
 * the refreshed numbers.
 *
 * The poll is a plain fetch, not a query: the query cache is persisted to
 * localStorage and a status must never outlive the page that asked for it.
 *
 * A ticker gets one cycle per mount. If its payload is flagged pending
 * again after the cycle ended, the worker is not delivering, and polling
 * again would loop forever.
 *
 * `isRefreshing` starts false on the server and on the first client render,
 * so the server HTML, the hydrated markup and what crawlers see all agree.
 */
export function useStatementRefresh(
  ticker: string,
  isRefreshPending: boolean,
): { isRefreshing: boolean } {
  const queryClient = useQueryClient();
  // The ticker being refreshed rather than a boolean, so a ticker change
  // can never leave the previous ticker's indicator showing.
  const [refreshingTicker, setRefreshingTicker] = useState<string | null>(null);
  const activeCycleRef = useRef<PollingCycle | null>(null);
  const finishedTickerRef = useRef<string | null>(null);

  useEffect(() => {
    return () => {
      if (activeCycleRef.current) cancelCycle(activeCycleRef.current);
      activeCycleRef.current = null;
      finishedTickerRef.current = null;
    };
  }, [ticker]);

  useEffect(() => {
    const hasCycleToStart =
      isRefreshPending &&
      activeCycleRef.current === null &&
      finishedTickerRef.current !== ticker;
    if (!hasCycleToStart) return;

    const cycle: PollingCycle = { isCancelled: false, timerId: null };
    activeCycleRef.current = cycle;
    setRefreshingTicker(ticker);

    function endCycle() {
      activeCycleRef.current = null;
      finishedTickerRef.current = ticker;
      setRefreshingTicker(null);
    }

    async function pollOnce(pollNumber: number) {
      const stillPending = await fetchIsRefreshPending(ticker);
      if (cycle.isCancelled) return;

      if (!stillPending) {
        await refetchRefreshedPayloads(queryClient, ticker);
        if (!cycle.isCancelled) endCycle();
      } else if (pollNumber >= MAX_STATUS_POLLS) {
        endCycle();
      } else {
        scheduleNextPoll(pollNumber + 1);
      }
    }

    function scheduleNextPoll(pollNumber: number) {
      cycle.timerId = setTimeout(() => pollOnce(pollNumber), STATUS_POLL_INTERVAL_MS);
    }

    scheduleNextPoll(1);
  }, [ticker, isRefreshPending, queryClient]);

  return { isRefreshing: refreshingTicker === ticker };
}
