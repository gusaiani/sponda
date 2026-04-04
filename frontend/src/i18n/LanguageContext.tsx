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

const SSR_DEFAULT: Locale = "pt";

export function LanguageProvider({ children }: { children: ReactNode }) {
  // Always start with "pt" to match the server render and avoid hydration mismatches.
  // The real locale is resolved in a useEffect after mount.
  const [locale, setLocaleState] = useState<Locale>(SSR_DEFAULT);

  const setLocale = useCallback((newLocale: Locale) => {
    setLocaleState(newLocale);
    localStorage.setItem(STORAGE_KEY, newLocale);
  }, []);

  // After hydration, resolve the real locale from localStorage or browser detection
  useEffect(() => {
    const resolved = getInitialLocale();
    if (resolved !== SSR_DEFAULT) {
      setLocaleState(resolved);
    }
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
