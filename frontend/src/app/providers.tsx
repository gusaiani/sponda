"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { PersistQueryClientProvider } from "@tanstack/react-query-persist-client";
import { createSyncStoragePersister } from "@tanstack/query-sync-storage-persister";
import { useState } from "react";
import { LanguageProvider } from "../i18n";
import { LearningModeProvider } from "../learning";
import type { Locale } from "../i18n/types";

interface ProvidersProps {
  children: React.ReactNode;
  locale: Locale;
}

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
      key: `sponda-react-query-cache-${QUERY_CACHE_VERSION}`,
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
