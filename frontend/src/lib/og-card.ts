import { formatNumber } from "../utils/format";
import { translateSector } from "../utils/sectorLabels";
import { translatorFor } from "../i18n/dictionaries";
import { djangoApiBaseUrl } from "./django-api";
import { fetchFromDjango } from "./django-fetch";
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
const RATIO_DECIMAL_PLACES = 2;

/** The three multiples are strict ten-year windows on the snapshot, so the labels are fixed. */
const PE10_LABEL = "PE10";
const PFCF10_LABEL = "PFCF10";
const PEG_LABEL = "PEG";
const MAX_TICKER_LENGTH = 12;
const IMAGE_EXTENSION = ".png";
const TICKER_PATTERN = new RegExp(`^[A-Z0-9.-]{1,${MAX_TICKER_LENGTH}}$`);

/**
 * The two artworks behind the site card, the image for pages with no single
 * company to render (homepage, screener). Only the tagline differs, so every
 * locale other than Portuguese shares the English file.
 */
export const SITE_OG_ARTWORKS = ["pt", "en"] as const;
export type SiteOgArtwork = (typeof SITE_OG_ARTWORKS)[number];
const SITE_OG_IMAGE_EXTENSION = ".jpg";
const SITE_OG_IMAGE_PATH = "/og/site";

export function siteOgArtworkForLocale(locale: string): SiteOgArtwork {
  return locale === "pt" ? "pt" : "en";
}

/** Public path of the site card in one language, e.g. `/og/site/en.jpg`. */
export function siteOgImageUrlForLocale(locale: string): string {
  return `${SITE_OG_IMAGE_PATH}/${siteOgArtworkForLocale(locale)}${SITE_OG_IMAGE_EXTENSION}`;
}

/** Recover the artwork from the route's filename segment, or null if it is not `<pt|en>.jpg`. */
export function siteOgArtworkFromParam(param: string): SiteOgArtwork | null {
  const match = SITE_OG_ARTWORKS.find((artwork) => param === `${artwork}${SITE_OG_IMAGE_EXTENSION}`);
  return match ?? null;
}

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

/**
 * The slice of `/api/tickers/{symbol}/indicators/` the card draws.
 *
 * That endpoint serves an `IndicatorSnapshot` row: two indexed reads and no
 * provider call, which is why it carries no lookup quota. `/api/quote/`
 * does, and it scopes anonymous callers by client IP. The Next server is
 * one IP, so when the card read the quote every company on the site shared
 * twenty lookups a day and then printed N/A in every slot for every
 * crawler. Same failure as the server-rendered page had, same cure the
 * markdown pages use; see "Why it is not built on `/api/quote/`" in the
 * README.
 *
 * The price is that earnings CAGR, which only the live quote computes, is
 * not available. Debt/Equity takes its tile: the snapshot has it for 86%
 * of companies, against 19% for PEG.
 */
export interface OgCardSnapshot {
  symbol?: string;
  name?: string | null;
  sector?: string | null;
  pe10?: number | null;
  pfcf10?: number | null;
  peg?: number | null;
  debt_to_equity?: number | null;
}

export interface OgCardData {
  name: string | null;
  sector: string | null;
  snapshot: OgCardSnapshot | null;
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
  snapshot: OgCardSnapshot | null;
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

/** Everything the card draws, resolved and formatted ahead of rendering. */
export function buildOgCardModel({
  ticker,
  locale,
  name,
  sector,
  snapshot,
}: OgCardModelInput): OgCardModel {
  const textLocale = ogCardTextLocale(locale);
  const translate = translatorFor(textLocale);
  const companyName = truncateCompanyName(name || snapshot?.name || ticker);
  const localizedSector = sector ? translateSector(sector, textLocale) : "";

  return {
    companyName,
    ticker,
    sector: localizedSector,
    subtitle: buildSubtitle(ticker, localizedSector, companyName),
    tagline: TAGLINES[locale],
    indicators: [
      {
        label: PE10_LABEL,
        value: formatIndicator(snapshot?.pe10, textLocale, INDICATOR_DECIMAL_PLACES),
      },
      {
        label: PFCF10_LABEL,
        value: formatIndicator(snapshot?.pfcf10, textLocale, INDICATOR_DECIMAL_PLACES),
      },
      {
        label: PEG_LABEL,
        value: formatIndicator(snapshot?.peg, textLocale, RATIO_DECIMAL_PLACES),
      },
      {
        label: translate("compare.col_debt_to_equity"),
        value: formatIndicator(snapshot?.debt_to_equity, textLocale, RATIO_DECIMAL_PLACES),
      },
    ],
  };
}

/** Social networks cache the image for a day at the edge anyway, so an hour is plenty. */
const CARD_DATA_REVALIDATE_SECONDS = 3600;

interface TickerIdentity {
  name?: string | null;
  sector?: string | null;
}

async function fetchJson<T>(url: string): Promise<T | null> {
  try {
    const response = await fetchFromDjango(url, {
      next: { revalidate: CARD_DATA_REVALIDATE_SECONDS },
    });
    if (!response || !response.ok) return null;
    return (await response.json()) as T;
  } catch {
    return null;
  }
}

/**
 * Company identity plus headline indicators for one ticker.
 *
 * The snapshot endpoint carries the identity too, but it answers 404 for a
 * fund, an ETF or a company with no market cap, and those still deserve a
 * card with their name on it. So the ticker endpoint is asked in parallel
 * and each source degrades on its own: a card with a company name and no
 * numbers still beats no card at all.
 */
export async function fetchOgCardData(ticker: string): Promise<OgCardData> {
  const baseUrl = djangoApiBaseUrl();
  const [snapshot, tickerIdentity] = await Promise.all([
    fetchJson<OgCardSnapshot>(`${baseUrl}/api/tickers/${ticker}/indicators/`),
    fetchJson<TickerIdentity>(`${baseUrl}/api/tickers/${ticker}/`),
  ]);

  return {
    name: snapshot?.name || tickerIdentity?.name || null,
    sector: snapshot?.sector || tickerIdentity?.sector || null,
    snapshot,
  };
}
