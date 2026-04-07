/** Locale configuration — shared by middleware, server components, and client code.
 * No React dependencies so it can be imported anywhere. */

export const SUPPORTED_LOCALES = ["pt", "en"] as const;
export type SupportedLocale = (typeof SUPPORTED_LOCALES)[number];

export const DEFAULT_LOCALE: SupportedLocale = "en";

export const LOCALE_TO_HTML_LANG: Record<SupportedLocale, string> = {
  pt: "pt-BR",
  en: "en",
};

export const LOCALE_TO_OG_LOCALE: Record<SupportedLocale, string> = {
  pt: "pt_BR",
  en: "en_US",
};

export function isSupportedLocale(value: string): value is SupportedLocale {
  return SUPPORTED_LOCALES.includes(value as SupportedLocale);
}

/** Detect locale from Accept-Language header. */
export function detectLocaleFromHeader(acceptLanguage: string | null): SupportedLocale {
  if (!acceptLanguage) return DEFAULT_LOCALE;
  const lower = acceptLanguage.toLowerCase();
  if (lower.startsWith("pt")) return "pt";
  // Check for pt anywhere in the preference list
  for (const part of lower.split(",")) {
    if (part.trim().startsWith("pt")) return "pt";
  }
  return DEFAULT_LOCALE;
}
