import { LOCALE_TO_HTML_LANG, isSupportedLocale } from "../lib/i18n-config";
import { isBrazilianTicker } from "./ticker";

/** ISO 4217 → display symbol. Long tail falls back to the code itself. */
const ISO_TO_SYMBOL: Record<string, string> = {
  USD: "$",
  BRL: "R$",
  EUR: "€",
  GBP: "£",
  JPY: "¥",
  CNY: "¥",
  DKK: "kr.",
  SEK: "kr.",
  NOK: "kr.",
  CHF: "Fr.",
  CAD: "$",
  AUD: "$",
  TWD: "NT$",
  HKD: "HK$",
  KRW: "₩",
  INR: "₹",
  MXN: "$",
  SGD: "S$",
};

/** Look up an ISO 4217 currency code's display symbol. */
export function currencySymbolForCode(code: string): string {
  const upper = code.toUpperCase();
  return ISO_TO_SYMBOL[upper] ?? upper;
}

/** Return the currency symbol for a given ticker.
 * If `reportedCurrency` is supplied, that takes precedence (foreign-listed
 * companies that file in a different currency than they trade in). Without
 * it, falls back to the listing-currency guess from the symbol pattern.
 */
export function currencySymbol(ticker: string, reportedCurrency?: string): string {
  if (reportedCurrency) {
    return currencySymbolForCode(reportedCurrency);
  }
  return isBrazilianTicker(ticker) ? "R$" : "$";
}

/** Return the ISO 4217 currency code for a given ticker.
 * If `reportedCurrency` is supplied, that takes precedence.
 */
export function currencyCode(ticker: string, reportedCurrency?: string): string {
  if (reportedCurrency) {
    return reportedCurrency.toUpperCase();
  }
  return isBrazilianTicker(ticker) ? "BRL" : "USD";
}

/** Proxied logo URL served from our server. */
export function logoUrl(symbol: string): string {
  return `/api/logos/${symbol}.png`;
}

/** Map backend labels (PE10, PFCF7…) to locale-appropriate equivalents.
 * Portuguese: PE10 → P/L10, PFCF10 → P/FCL10
 * English: keeps the original (PE10, PFCF10)
 */
export function localizeLabel(label: string, locale: string): string {
  if (locale === "pt") {
    return label.replace(/^PE/, "P/L").replace(/^PFCF/, "P/FCL");
  }
  return label;
}

/** @deprecated Use localizeLabel(label, locale) instead */
export function ptLabel(label: string): string {
  return localizeLabel(label, "pt");
}

function bcp47(locale: string): string {
  return isSupportedLocale(locale) ? LOCALE_TO_HTML_LANG[locale] : "en";
}

/** Format a number using the given locale's decimal/thousand conventions.
 * Hyphen-minus is replaced with an en-dash for a more typographic look. */
export function formatNumber(n: number, digits: number, locale: string): string {
  return n
    .toLocaleString(bcp47(locale), {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    })
    .replace("-", "–");
}

export function formatLargeNumber(
  value: number,
  ticker: string = "",
  locale: string = "en",
  reportedCurrency?: string,
): string {
  const currency = ticker || reportedCurrency
    ? currencySymbol(ticker, reportedCurrency)
    : "R$";
  const abs = Math.abs(value);
  if (abs >= 1e9) return `${currency} ${formatNumber(value / 1e9, 2, locale)}B`;
  if (abs >= 1e6) return `${currency} ${formatNumber(value / 1e6, 2, locale)}M`;
  if (abs >= 1e3) return `${currency} ${formatNumber(value / 1e3, 1, locale)}K`;
  return `${currency} ${formatNumber(value, 0, locale)}`;
}

export function formatQuarterLabel(dateStr: string): string {
  const [year, month] = dateStr.split("-").map(Number);
  const q = Math.ceil(month / 3);
  return `${q}T${year}`;
}

/**
 * Return today's date as a YYYY-MM-DD string in the user's local timezone.
 *
 * Unlike `new Date().toISOString().slice(0, 10)`, which returns the UTC date,
 * this returns the local date, matching the server's `date.today()` behavior.
 */
export function localToday(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}
