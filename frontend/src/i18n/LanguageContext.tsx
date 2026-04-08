"use client";

import { createContext, useCallback, useEffect, useState, type ReactNode } from "react";
import type { Locale } from "./types";

const STORAGE_KEY = "sponda-lang";

interface LanguageContextValue {
  locale: Locale;
  setLocale: (locale: Locale) => void;
}

export const LanguageContext = createContext<LanguageContextValue>({
  locale: "en",
  setLocale: () => {},
});

interface LanguageProviderProps {
  children: ReactNode;
  initialLocale: Locale;
}

export function LanguageProvider({ children, initialLocale }: LanguageProviderProps) {
  const [locale, setLocaleState] = useState<Locale>(initialLocale);

  // Keep state in sync if initialLocale changes (e.g. navigation)
  useEffect(() => {
    if (initialLocale !== locale) {
      setLocaleState(initialLocale);
    }
  }, [initialLocale]); // eslint-disable-line react-hooks/exhaustive-deps

  const setLocale = useCallback((newLocale: Locale) => {
    setLocaleState(newLocale);
    localStorage.setItem(STORAGE_KEY, newLocale);
    // Navigation is handled by the LanguageToggle component
  }, []);

  // Sync html lang attribute
  useEffect(() => {
    const HTML_LANG: Record<string, string> = { pt: "pt-BR", en: "en", es: "es", zh: "zh-CN", fr: "fr", de: "de" };
    document.documentElement.lang = HTML_LANG[locale] || "en";
  }, [locale]);

  return (
    <LanguageContext.Provider value={{ locale, setLocale }}>
      {children}
    </LanguageContext.Provider>
  );
}
