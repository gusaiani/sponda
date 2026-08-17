import { formatNumber } from "../utils/format";
import { translateSector } from "../utils/sectorLabels";
import { djangoApiBaseUrl } from "./django-api";
import type { SupportedLocale } from "./i18n-config";

import { de } from "../i18n/locales/de";
import { en } from "../i18n/locales/en";
import { es } from "../i18n/locales/es";
import { fr } from "../i18n/locales/fr";
import { it } from "../i18n/locales/it";
import { pt } from "../i18n/locales/pt";

/** Card size, matching the `og:image:width` / `og:image:height` we advertise. */
export const OG_CARD_WIDTH = 1200;
export const OG_CARD_HEIGHT = 630;

/** Longest company name the headline can hold before it has to be cut. */
export const MAX_COMPANY_NAME_LENGTH = 32;

/** What the product prints when an indicator could not be computed. */
export const MISSING_VALUE = "N/A";

const INDICATOR_DECIMAL_PLACES = 1;
const PEG_DECIMAL_PLACES = 2;
const MAX_TICKER_LENGTH = 12;
const IMAGE_EXTENSION = ".png";
const TICKER_PATTERN = new RegExp(`^[A-Z0-9.-]{1,${MAX_TICKER_LENGTH}}$`);

/**
 * Locale the card's own words are drawn in.
 *
 * The card is rendered by satori using the Geist Regular face bundled with
 * `next/og`, which covers Latin scripts only. `zh` would come out as tofu
 * boxes, so its wording falls back to English; the numbers, the ticker and
 * the company name are identical either way.
 */
export function ogCardTextLocale(locale: SupportedLocale): SupportedLocale {
  return locale === "zh" ? "en" : locale;
}

const TAGLINES: Record<SupportedLocale, string> = {
  pt: pt["header.tagline"],
  en: en["header.tagline"],
  es: es["header.tagline"],
  fr: fr["header.tagline"],
  de: de["header.tagline"],
  it: it["header.tagline"],
  zh: en["header.tagline"],
};

/** Public path of the Open Graph card for one company in one language. */
export function ogImageUrlForTicker(locale: string, ticker: string): string {
  return `/og/${locale}/${ticker.toUpperCase()}${IMAGE_EXTENSION}`;
}

/**
 * Recover the ticker from the route's filename segment, or null if the
 * segment is not a plain `<TICKER>.png`.
 *
 * Requiring the extension keeps one image on exactly one URL, which matters
 * because social networks key their image caches by URL.
 */
export function tickerFromOgImageParam(param: string): string | null {
  if (!param.endsWith(IMAGE_EXTENSION)) return null;
  const ticker = param.slice(0, -IMAGE_EXTENSION.length).toUpperCase();
  return TICKER_PATTERN.test(ticker) ? ticker : null;
}

export interface OgCardQuote {
  name?: string | null;
  pe10?: number | null;
  pe10Label?: string | null;
  pfcf10?: number | null;
  pfcf10Label?: string | null;
  peg?: number | null;
  earningsCAGR?: number | null;
}

export interface OgCardData {
  name: string | null;
  sector: string | null;
  quote: OgCardQuote | null;
}

export interface OgCardIndicator {
  label: string;
  value: string;
}

export interface OgCardModel {
  companyName: string;
  ticker: string;
  sector: string;
  /** Line under the headline: ticker, plus the sector when there is one. */
  subtitle: string;
  tagline: string;
  indicators: OgCardIndicator[];
}

/**
 * The line under the headline.
 *
 * Empty when it would only repeat the headline, which happens for a ticker
 * the API knows nothing about: with no company name the headline is already
 * the symbol.
 */
function buildSubtitle(ticker: string, sector: string, companyName: string): string {
  if (sector) return `${ticker} · ${sector}`;
  return companyName === ticker ? "" : ticker;
}

interface OgCardModelInput {
  ticker: string;
  locale: SupportedLocale;
  name: string | null;
  sector: string | null;
  quote: OgCardQuote | null;
}

function truncateCompanyName(name: string): string {
  return name.length <= MAX_COMPANY_NAME_LENGTH
    ? name
    : `${name.slice(0, MAX_COMPANY_NAME_LENGTH)}…`;
}

function formatIndicator(
  value: number | null | undefined,
  locale: SupportedLocale,
  decimalPlaces: number,
): string {
  return typeof value === "number" && Number.isFinite(value)
    ? formatNumber(value, decimalPlaces, locale)
    : MISSING_VALUE;
}

function formatPercentage(
  value: number | null | undefined,
  locale: SupportedLocale,
): string {
  return typeof value === "number" && Number.isFinite(value)
    ? `${formatNumber(value, INDICATOR_DECIMAL_PLACES, locale)}%`
    : MISSING_VALUE;
}

/** Everything the card draws, resolved and formatted ahead of rendering. */
export function buildOgCardModel({
  ticker,
  locale,
  name,
  sector,
  quote,
}: OgCardModelInput): OgCardModel {
  const textLocale = ogCardTextLocale(locale);
  const companyName = truncateCompanyName(name || quote?.name || ticker);
  const localizedSector = sector ? translateSector(sector, textLocale) : "";

  return {
    companyName,
    ticker,
    sector: localizedSector,
    subtitle: buildSubtitle(ticker, localizedSector, companyName),
    tagline: TAGLINES[locale],
    indicators: [
      {
        label: quote?.pe10Label || "PE10",
        value: formatIndicator(quote?.pe10, textLocale, INDICATOR_DECIMAL_PLACES),
      },
      {
        label: quote?.pfcf10Label || "PFCF10",
        value: formatIndicator(quote?.pfcf10, textLocale, INDICATOR_DECIMAL_PLACES),
      },
      {
        label: "PEG",
        value: formatIndicator(quote?.peg, textLocale, PEG_DECIMAL_PLACES),
      },
      {
        label: "CAGR",
        value: formatPercentage(quote?.earningsCAGR, textLocale),
      },
    ],
  };
}

const QUOTE_REVALIDATE_SECONDS = 3600;

async function fetchJson<T>(url: string): Promise<T | null> {
  try {
    const response = await fetch(url, { next: { revalidate: QUOTE_REVALIDATE_SECONDS } });
    if (!response.ok) return null;
    return (await response.json()) as T;
  } catch {
    return null;
  }
}

/**
 * Company identity plus headline indicators for one ticker.
 *
 * Never rejects: a card with a company name and no numbers still beats no
 * card at all, so each endpoint degrades on its own.
 */
export async function fetchOgCardData(ticker: string): Promise<OgCardData> {
  const baseUrl = djangoApiBaseUrl();
  const [tickerInfo, quote] = await Promise.all([
    fetchJson<{ name?: string; sector?: string }>(`${baseUrl}/api/tickers/${ticker}/`),
    fetchJson<OgCardQuote>(`${baseUrl}/api/quote/${ticker}/`),
  ]);

  return {
    name: tickerInfo?.name ?? null,
    sector: tickerInfo?.sector ?? null,
    quote,
  };
}
