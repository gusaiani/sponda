import { isBrazilianTicker } from "./ticker";

/** Return the currency symbol for a given ticker. */
export function currencySymbol(ticker: string): string {
  return isBrazilianTicker(ticker) ? "R$" : "$";
}

/** Proxied logo URL served from our server. */
export function logoUrl(symbol: string): string {
  return `/api/logos/${symbol}.png`;
}

/** Map backend labels (PE10, PFCF7…) to Portuguese equivalents */
export function ptLabel(label: string): string {
  return label.replace(/^PE/, "P/L").replace(/^PFCF/, "P/FCL");
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
