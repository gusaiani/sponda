"use client";

import { createContext, useCallback, useEffect, useState, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import type { Locale } from "./types";
import { translateTabSlug } from "../utils/tabs";

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
  const router = useRouter();
  const pathname = usePathname();

  // Keep state in sync if initialLocale changes (e.g. navigation)
  useEffect(() => {
    if (initialLocale !== locale) {
      setLocaleState(initialLocale);
    }
  }, [initialLocale]); // eslint-disable-line react-hooks/exhaustive-deps

  const setLocale = useCallback((newLocale: Locale) => {
    setLocaleState(newLocale);
    localStorage.setItem(STORAGE_KEY, newLocale);

    // Navigate to the equivalent URL in the new locale
    const segments = pathname.split("/").filter(Boolean);
    // segments[0] is the current locale prefix
    if (segments.length > 0 && (segments[0] === "pt" || segments[0] === "en")) {
      segments[0] = newLocale;
      // Translate tab slug if present (3rd segment: /{locale}/{ticker}/{tab})
      if (segments.length === 3) {
        segments[2] = translateTabSlug(segments[2], newLocale);
      }
    } else {
      // No locale prefix — prepend
      segments.unshift(newLocale);
    }
    router.push("/" + segments.join("/"));
  }, [pathname, router]);

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
