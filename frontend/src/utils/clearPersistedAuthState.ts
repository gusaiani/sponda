/**
 * Tears down all client-side traces of an authenticated session so the
 * next page load starts cold. Used by logout and any other "I am no
 * longer this user" flow.
 *
 * The React Query cache is persisted to localStorage by
 * PersistQueryClientProvider; every user-scoped query key (auth-user,
 * favorites, saved-lists, homepage-layout, …) lives there for 24h.
 * Clearing only the in-memory client is not enough — the persister
 * rehydrates the stale values on the very next mount.
 */

import type { QueryClient } from "@tanstack/react-query";

export const PERSISTED_QUERY_CACHE_KEY = "sponda-react-query-cache-v1";

interface AssignableLocation {
  href: string;
}

interface RemovableStorage {
  removeItem(key: string): void;
}

export function clearPersistedAuthState({
  queryClient,
  storage,
  navigator,
}: {
  queryClient: Pick<QueryClient, "clear">;
  storage: RemovableStorage;
  navigator: AssignableLocation;
}): void {
  queryClient.clear();
  storage.removeItem(PERSISTED_QUERY_CACHE_KEY);
  navigator.href = "/";
}
