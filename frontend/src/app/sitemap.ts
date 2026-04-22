import type { MetadataRoute } from "next";
import { SUPPORTED_LOCALES } from "../lib/i18n-config";
import { tabSlugForLocale, type TabKey } from "../utils/tabs";
import { getPopularSymbols } from "../utils/suggestedCompanies";

const BASE_URL = "https://sponda.capital";
const DJANGO_API_URL = process.env.DJANGO_API_URL || "http://localhost:8710";

const TAB_KEYS: TabKey[] = ["charts", "fundamentals", "compare"];
const TICKERS_PER_SITEMAP = 1500;

const FEATURED_TICKERS = [...new Set([
  ...getPopularSymbols("brazil"),
  ...getPopularSymbols("us"),
  ...getPopularSymbols("europe"),
  ...getPopularSymbols("asia"),
])];

const FEATURED_SET = new Set(FEATURED_TICKERS);

interface TickerEntry {
  symbol: string;
}

async function fetchAllTickers(): Promise<string[]> {
  try {
    const response = await fetch(`${DJANGO_API_URL}/api/tickers/all/`, {
      next: { revalidate: 86400 },
    });
    if (!response.ok) return [];
    const tickers: TickerEntry[] = await response.json();
    return tickers.map((ticker) => ticker.symbol);
  } catch {
    return [];
  }
}

function buildAlternates(pathBuilder: (locale: string) => string): Record<string, string> {
  const languages: Record<string, string> = {};
  for (const locale of SUPPORTED_LOCALES) {
    const key = locale === "pt" ? "pt-BR" : locale;
    languages[key] = `${BASE_URL}${pathBuilder(locale)}`;
  }
  languages["x-default"] = `${BASE_URL}${pathBuilder("en")}`;
  return languages;
}

function tickerEntries(
  tickers: string[],
  mainPriority: number,
  tabPriority: number,
  lastModified: string,
): MetadataRoute.Sitemap {
  const entries: MetadataRoute.Sitemap = [];

  for (const ticker of tickers) {
    for (const locale of SUPPORTED_LOCALES) {
      entries.push({
        url: `${BASE_URL}/${locale}/${ticker}`,
        lastModified,
        alternates: {
          languages: buildAlternates((loc) => `/${loc}/${ticker}`),
        },
        changeFrequency: "daily",
        priority: mainPriority,
      });
    }

    for (const tabKey of TAB_KEYS) {
      for (const locale of SUPPORTED_LOCALES) {
        const slug = tabSlugForLocale(locale, tabKey);
        entries.push({
          url: `${BASE_URL}/${locale}/${ticker}/${slug}`,
          lastModified,
          alternates: {
            languages: buildAlternates(
              (loc) => `/${loc}/${ticker}/${tabSlugForLocale(loc, tabKey)}`,
            ),
          },
          changeFrequency: "daily",
          priority: tabPriority,
        });
      }
    }
  }

  return entries;
}

export async function generateSitemaps() {
  const allTickers = await fetchAllTickers();
  const remainingTickers = allTickers.filter((ticker) => !FEATURED_SET.has(ticker));
  const apiChunks = Math.ceil(remainingTickers.length / TICKERS_PER_SITEMAP);

  const ids = [{ id: 0 }, { id: 1 }];
  for (let i = 0; i < apiChunks; i++) {
    ids.push({ id: i + 2 });
  }
  return ids;
}

export default async function sitemap({
  id,
}: {
  id: number;
}): Promise<MetadataRoute.Sitemap> {
  const now = new Date().toISOString();

  if (id === 0) {
    const entries: MetadataRoute.Sitemap = [];

    for (const locale of SUPPORTED_LOCALES) {
      entries.push({
        url: `${BASE_URL}/${locale}`,
        lastModified: now,
        alternates: {
          languages: buildAlternates((loc) => `/${loc}`),
        },
        changeFrequency: "weekly",
        priority: 1.0,
      });
    }

    for (const locale of SUPPORTED_LOCALES) {
      entries.push({
        url: `${BASE_URL}/${locale}/screener`,
        lastModified: now,
        alternates: {
          languages: buildAlternates((loc) => `/${loc}/screener`),
        },
        changeFrequency: "weekly",
        priority: 0.8,
      });
    }

    return entries;
  }

  if (id === 1) {
    return tickerEntries(FEATURED_TICKERS, 0.9, 0.7, now);
  }

  const allTickers = await fetchAllTickers();
  const remainingTickers = allTickers.filter((ticker) => !FEATURED_SET.has(ticker));
  const pageIndex = id - 2;
  const start = pageIndex * TICKERS_PER_SITEMAP;
  const chunk = remainingTickers.slice(start, start + TICKERS_PER_SITEMAP);

  return tickerEntries(chunk, 0.7, 0.5, now);
}
