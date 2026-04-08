import type { MetadataRoute } from "next";
import { SUPPORTED_LOCALES, LOCALE_TO_HTML_LANG } from "../lib/i18n-config";
import { tabSlugForLocale, type TabKey } from "../utils/tabs";

const BASE_URL = "https://sponda.capital";
const DJANGO_API_URL = process.env.DJANGO_API_URL || "http://localhost:8710";

const TAB_KEYS: TabKey[] = ["charts", "fundamentals", "compare"];

interface TickerEntry {
  symbol: string;
}

async function fetchAllTickers(): Promise<string[]> {
  try {
    const response = await fetch(`${DJANGO_API_URL}/api/tickers/all/`, { next: { revalidate: 86400 } });
    if (!response.ok) return [];
    const tickers: TickerEntry[] = await response.json();
    return tickers.map((ticker) => ticker.symbol);
  } catch {
    return [];
  }
}

/** Build hreflang alternates for a given path builder function. */
function buildAlternates(pathBuilder: (locale: string) => string): Record<string, string> {
  const languages: Record<string, string> = {};
  for (const locale of SUPPORTED_LOCALES) {
    const key = locale === "pt" ? "pt-BR" : locale;
    languages[key] = `${BASE_URL}${pathBuilder(locale)}`;
  }
  languages["x-default"] = `${BASE_URL}${pathBuilder("en")}`;
  return languages;
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const tickers = await fetchAllTickers();

  const staticPages = ["", "/login", "/signup"];
  const entries: MetadataRoute.Sitemap = [];

  // Static pages in all locales
  for (const page of staticPages) {
    for (const locale of SUPPORTED_LOCALES) {
      entries.push({
        url: `${BASE_URL}/${locale}${page}`,
        alternates: {
          languages: buildAlternates((loc) => `/${loc}${page}`),
        },
        changeFrequency: "weekly",
        priority: page === "" ? 1.0 : 0.3,
      });
    }
  }

  // Ticker pages in all locales
  for (const ticker of tickers) {
    // Main ticker page
    for (const locale of SUPPORTED_LOCALES) {
      entries.push({
        url: `${BASE_URL}/${locale}/${ticker}`,
        alternates: {
          languages: buildAlternates((loc) => `/${loc}/${ticker}`),
        },
        changeFrequency: "daily",
        priority: 0.8,
      });
    }

    // Tab pages
    for (const tabKey of TAB_KEYS) {
      for (const locale of SUPPORTED_LOCALES) {
        const slug = tabSlugForLocale(locale, tabKey);
        entries.push({
          url: `${BASE_URL}/${locale}/${ticker}/${slug}`,
          alternates: {
            languages: buildAlternates((loc) => `/${loc}/${ticker}/${tabSlugForLocale(loc, tabKey)}`),
          },
          changeFrequency: "daily",
          priority: 0.6,
        });
      }
    }
  }

  return entries;
}
