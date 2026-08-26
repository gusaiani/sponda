"use client";

import { useContext, useCallback } from "react";
import { LanguageContext } from "./LanguageContext";
import { DICTIONARIES, translate } from "./dictionaries";
import type { TranslationKey } from "./types";

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
    (key: TranslationKey, params?: Record<string, string | number>): string =>
      translate(dictionary, key, params),
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
