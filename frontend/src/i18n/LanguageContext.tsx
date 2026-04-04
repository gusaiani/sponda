"use client";

import { createContext, useCallback, useEffect, useState, type ReactNode } from "react";
import type { Locale } from "./types";

const STORAGE_KEY = "sponda-lang";

interface LanguageContextValue {
  locale: Locale;
  setLocale: (locale: Locale) => void;
}

export const LanguageContext = createContext<LanguageContextValue>({
  locale: "pt",
  setLocale: () => {},
});

function detectBrowserLocale(): Locale {
  if (typeof navigator === "undefined") return "pt";

  const languages = navigator.languages ?? [navigator.language];
  for (const language of languages) {
    const lower = language.toLowerCase();
    if (lower.startsWith("pt")) return "pt";
    if (lower.startsWith("en")) return "en";
  }

  return "en";
}

function getInitialLocale(): Locale {
  if (typeof window === "undefined") return "pt";

  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === "pt" || stored === "en") return stored;

  return detectBrowserLocale();
}

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(getInitialLocale);

  const setLocale = useCallback((newLocale: Locale) => {
    setLocaleState(newLocale);
    localStorage.setItem(STORAGE_KEY, newLocale);
  }, []);

  // Sync html lang attribute
  useEffect(() => {
    const htmlLang = locale === "pt" ? "pt-BR" : "en";
    document.documentElement.lang = htmlLang;
  }, [locale]);

  return (
    <LanguageContext.Provider value={{ locale, setLocale }}>
      {children}
    </LanguageContext.Provider>
  );
}
