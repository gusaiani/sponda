import type { MetadataRoute } from "next";
import { SUPPORTED_LOCALES } from "../lib/i18n-config";
import { getPopularSymbols } from "../utils/suggestedCompanies";
import { tabSlugForLocale, type TabKey } from "../utils/tabs";

const BASE_URL = "https://sponda.capital";
const REGIONS = ["brazil", "us", "europe", "asia"] as const;
const TAB_KEYS: readonly TabKey[] = ["charts", "fundamentals", "compare"];

const CURATED_TICKERS = [...new Set(
  REGIONS.flatMap((region) => getPopularSymbols(region)),
)];

function buildAlternates(pathBuilder: (locale: string) => string): Record<string, string> {
  const languages: Record<string, string> = {};

  for (const locale of SUPPORTED_LOCALES) {
    const key = locale === "pt" ? "pt-BR" : locale;
    languages[key] = `${BASE_URL}${pathBuilder(locale)}`;
  }

  languages["x-default"] = `${BASE_URL}${pathBuilder("en")}`;
  return languages;
}

function buildLocalizedEntries(
  pathBuilder: (locale: string) => string,
  priority: number,
  changeFrequency: "daily" | "weekly",
  lastModified: string,
): MetadataRoute.Sitemap {
  return SUPPORTED_LOCALES.map((locale) => ({
    url: `${BASE_URL}${pathBuilder(locale)}`,
    lastModified,
    alternates: {
      languages: buildAlternates(pathBuilder),
    },
    changeFrequency,
    priority,
  }));
}

function buildCompanyEntries(lastModified: string): MetadataRoute.Sitemap {
  const entries: MetadataRoute.Sitemap = [];

  for (const ticker of CURATED_TICKERS) {
    entries.push(
      ...buildLocalizedEntries((locale) => `/${locale}/${ticker}`, 0.9, "daily", lastModified),
    );

    for (const tabKey of TAB_KEYS) {
      entries.push(
        ...buildLocalizedEntries(
          (locale) => `/${locale}/${ticker}/${tabSlugForLocale(locale, tabKey)}`,
          0.7,
          "daily",
          lastModified,
        ),
      );
    }
  }

  return entries;
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const lastModified = new Date().toISOString();

  return [
    ...buildLocalizedEntries((locale) => `/${locale}`, 1.0, "weekly", lastModified),
    ...buildLocalizedEntries((locale) => `/${locale}/screener`, 0.8, "weekly", lastModified),
    ...buildCompanyEntries(lastModified),
  ];
}
