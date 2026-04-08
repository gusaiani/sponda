/** Locale configuration — shared by middleware, server components, and client code.
 * No React dependencies so it can be imported anywhere. */

export const SUPPORTED_LOCALES = ["pt", "en", "es", "zh", "fr", "de", "it"] as const;
export type SupportedLocale = (typeof SUPPORTED_LOCALES)[number];

export const DEFAULT_LOCALE: SupportedLocale = "en";

export const LOCALE_TO_HTML_LANG: Record<SupportedLocale, string> = {
  pt: "pt-BR",
  en: "en",
  es: "es",
  zh: "zh-CN",
  fr: "fr",
  de: "de",
  it: "it",
};

export const LOCALE_TO_OG_LOCALE: Record<SupportedLocale, string> = {
  pt: "pt_BR",
  en: "en_US",
  es: "es_ES",
  zh: "zh_CN",
  fr: "fr_FR",
  de: "de_DE",
  it: "it_IT",
};

export function isSupportedLocale(value: string): value is SupportedLocale {
  return SUPPORTED_LOCALES.includes(value as SupportedLocale);
}

/** Mapping from Accept-Language prefix to supported locale. */
const LANG_PREFIX_TO_LOCALE: [string, SupportedLocale][] = [
  ["pt", "pt"],
  ["es", "es"],
  ["zh", "zh"],
  ["fr", "fr"],
  ["de", "de"],
  ["it", "it"],
];

/** Detect locale from Accept-Language header. */
export function detectLocaleFromHeader(acceptLanguage: string | null): SupportedLocale {
  if (!acceptLanguage) return DEFAULT_LOCALE;
  const parts = acceptLanguage.toLowerCase().split(",");
  for (const part of parts) {
    const lang = part.trim().split(";")[0].trim();
    for (const [prefix, locale] of LANG_PREFIX_TO_LOCALE) {
      if (lang.startsWith(prefix)) return locale;
    }
  }
  return DEFAULT_LOCALE;
}
