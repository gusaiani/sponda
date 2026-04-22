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

  const setLocale = useCallback((newLocale: Locale) => {
    setLocaleState(newLocale);
    localStorage.setItem(STORAGE_KEY, newLocale);
    // Set cookie so middleware can read the preference on subsequent visits
    document.cookie = `${STORAGE_KEY}=${newLocale};path=/;max-age=${365 * 24 * 60 * 60};SameSite=Lax`;
    // Persist to backend so the preference survives across devices for
    // authenticated users. Anonymous visitors get 401 — ignore it.
    fetch("/api/auth/language/", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ language: newLocale }),
    }).catch(() => {});
    // Navigation is handled by the LanguageToggle component
  }, []);

  // URL-driven locale change (user clicked an /it link, typed /fr in the
  // address bar, etc.) should be treated as the user's new preference:
  // persist it to the cookie and the backend. Defined after `setLocale` so
  // the effect can call it. Runs when `initialLocale` changes — on mount
  // `initialLocale === locale` so this is a no-op.
  useEffect(() => {
    if (initialLocale !== locale) {
      setLocale(initialLocale);
    }
  }, [initialLocale]); // eslint-disable-line react-hooks/exhaustive-deps

  // Sync html lang attribute
  useEffect(() => {
    const HTML_LANG: Record<string, string> = { pt: "pt-BR", en: "en", es: "es", zh: "zh-CN", fr: "fr", de: "de", it: "it" };
    document.documentElement.lang = HTML_LANG[locale] || "en";
  }, [locale]);

  return (
    <LanguageContext.Provider value={{ locale, setLocale }}>
      {children}
    </LanguageContext.Provider>
  );
}
