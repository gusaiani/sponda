"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { PersistQueryClientProvider } from "@tanstack/react-query-persist-client";
import { createSyncStoragePersister } from "@tanstack/query-sync-storage-persister";
import { useState } from "react";
import { LanguageProvider } from "../i18n";
import { LearningModeProvider } from "../learning";
import { PERSISTED_QUERY_CACHE_KEY } from "../utils/clearPersistedAuthState";
import type { Locale } from "../i18n/types";

interface ProvidersProps {
  children: React.ReactNode;
  locale: Locale;
}

// The storage key already encodes the cache version (v1); bumping the
// suffix in PERSISTED_QUERY_CACHE_KEY busts every client's cached state.
// QUERY_CACHE_VERSION below is the buster passed to PersistQueryClient;
// keep it in sync with the suffix on PERSISTED_QUERY_CACHE_KEY.
const QUERY_CACHE_VERSION = "v1";
// 24 hours: long enough that returning visitors render the home page
// instantly from localStorage, short enough that an FX rebrand or
// indicator-methodology change rolls out within a day.
const PERSIST_MAX_AGE_MS = 24 * 60 * 60 * 1000;

export function Providers({ children, locale }: ProvidersProps) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            // gcTime must exceed the persister's maxAge or rehydrated
            // entries get evicted before they render.
            gcTime: PERSIST_MAX_AGE_MS,
          },
        },
      }),
  );
  const [persister] = useState(() => {
    if (typeof window === "undefined") return null;
    return createSyncStoragePersister({
      storage: window.localStorage,
      key: PERSISTED_QUERY_CACHE_KEY,
      throttleTime: 1000,
    });
  });

  const inner = (
    <LearningModeProvider>{children}</LearningModeProvider>
  );

  return (
    <LanguageProvider initialLocale={locale}>
      {persister ? (
        <PersistQueryClientProvider
          client={queryClient}
          persistOptions={{
            persister,
            maxAge: PERSIST_MAX_AGE_MS,
            buster: QUERY_CACHE_VERSION,
          }}
        >
          {inner}
        </PersistQueryClientProvider>
      ) : (
        <QueryClientProvider client={queryClient}>{inner}</QueryClientProvider>
      )}
    </LanguageProvider>
  );
}
