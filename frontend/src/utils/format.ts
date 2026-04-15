import { isBrazilianTicker } from "./ticker";

/** Return the currency symbol for a given ticker. */
export function currencySymbol(ticker: string): string {
  return isBrazilianTicker(ticker) ? "R$" : "$";
}

/** Return the ISO 4217 currency code for a given ticker. */
export function currencyCode(ticker: string): string {
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

/** Format number with Brazilian notation: period for thousands, comma for decimals */
export function br(n: number, digits: number): string {
  return n.toLocaleString("pt-BR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).replace("-", "\u2013");
}

export function formatLargeNumber(value: number, ticker: string = ""): string {
  const currency = ticker ? currencySymbol(ticker) : "R$";
  const abs = Math.abs(value);
  if (abs >= 1e9) return `${currency} ${br(value / 1e9, 2)}B`;
  if (abs >= 1e6) return `${currency} ${br(value / 1e6, 2)}M`;
  if (abs >= 1e3) return `${currency} ${br(value / 1e3, 1)}K`;
  return `${currency} ${br(value, 0)}`;
}

export function formatQuarterLabel(dateStr: string): string {
  const [year, month] = dateStr.split("-").map(Number);
  const q = Math.ceil(month / 3);
  return `${q}T${year}`;
}
