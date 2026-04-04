"use client";

import { useContext, useCallback } from "react";
import { LanguageContext } from "./LanguageContext";
import { pt } from "./locales/pt";
import { en } from "./locales/en";
import type { Locale, TranslationKey, TranslationDictionary } from "./types";

const DICTIONARIES: Record<Locale, TranslationDictionary> = { pt, en };

/**
 * Returns:
 * - `t(key)` — look up a translation string
 * - `t(key, params)` — look up and interpolate `{param}` placeholders
 * - `locale` — current locale
 * - `setLocale` — change locale
 * - `pluralize(count, singular, plural)` — returns singular or plural form
 */
export function useTranslation() {
  const { locale, setLocale } = useContext(LanguageContext);
  const dictionary = DICTIONARIES[locale];

  const t = useCallback(
    (key: TranslationKey, params?: Record<string, string | number>): string => {
      let value = dictionary[key];
      if (params) {
        for (const [paramKey, paramValue] of Object.entries(params)) {
          value = value.replace(new RegExp(`\\{${paramKey}\\}`, "g"), String(paramValue));
        }
      }
      return value;
    },
    [dictionary],
  );

  const pluralize = useCallback(
    (count: number, singularKey: TranslationKey, pluralKey: TranslationKey): string => {
      return count === 1 ? dictionary[singularKey] : dictionary[pluralKey];
    },
    [dictionary],
  );

  return { t, locale, setLocale, pluralize } as const;
}
