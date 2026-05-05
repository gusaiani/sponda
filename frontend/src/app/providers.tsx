"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { LanguageProvider } from "../i18n";
import { LearningModeProvider } from "../learning";
import type { Locale } from "../i18n/types";

interface ProvidersProps {
  children: React.ReactNode;
  locale: Locale;
}

export function Providers({ children, locale }: ProvidersProps) {
  const [queryClient] = useState(() => new QueryClient());

  return (
    <LanguageProvider initialLocale={locale}>
      <QueryClientProvider client={queryClient}>
        <LearningModeProvider>
          {children}
        </LearningModeProvider>
      </QueryClientProvider>
    </LanguageProvider>
  );
}
