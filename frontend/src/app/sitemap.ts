import type { MetadataRoute } from "next";

const BASE_URL = "https://sponda.capital";
const DJANGO_API_URL = process.env.DJANGO_API_URL || "http://localhost:8710";

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

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const tickers = await fetchAllTickers();

  const staticPages = ["", "/login", "/signup"];
  const tabSlugs = {
    pt: ["fundamentos", "comparar", "graficos"],
    en: ["fundamentals", "compare", "charts"],
  };

  const entries: MetadataRoute.Sitemap = [];

  // Static pages in both locales
  for (const page of staticPages) {
    entries.push({
      url: `${BASE_URL}/en${page}`,
      alternates: {
        languages: {
          "pt-BR": `${BASE_URL}/pt${page}`,
          en: `${BASE_URL}/en${page}`,
        },
      },
      changeFrequency: "weekly",
      priority: page === "" ? 1.0 : 0.3,
    });
    entries.push({
      url: `${BASE_URL}/pt${page}`,
      alternates: {
        languages: {
          "pt-BR": `${BASE_URL}/pt${page}`,
          en: `${BASE_URL}/en${page}`,
        },
      },
      changeFrequency: "weekly",
      priority: page === "" ? 1.0 : 0.3,
    });
  }

  // Ticker pages in both locales
  for (const ticker of tickers) {
    // Main ticker page
    entries.push({
      url: `${BASE_URL}/en/${ticker}`,
      alternates: {
        languages: {
          "pt-BR": `${BASE_URL}/pt/${ticker}`,
          en: `${BASE_URL}/en/${ticker}`,
        },
      },
      changeFrequency: "daily",
      priority: 0.8,
    });
    entries.push({
      url: `${BASE_URL}/pt/${ticker}`,
      alternates: {
        languages: {
          "pt-BR": `${BASE_URL}/pt/${ticker}`,
          en: `${BASE_URL}/en/${ticker}`,
        },
      },
      changeFrequency: "daily",
      priority: 0.8,
    });

    // Tab pages
    for (let tabIndex = 0; tabIndex < tabSlugs.en.length; tabIndex++) {
      const enSlug = tabSlugs.en[tabIndex];
      const ptSlug = tabSlugs.pt[tabIndex];

      entries.push({
        url: `${BASE_URL}/en/${ticker}/${enSlug}`,
        alternates: {
          languages: {
            "pt-BR": `${BASE_URL}/pt/${ticker}/${ptSlug}`,
            en: `${BASE_URL}/en/${ticker}/${enSlug}`,
          },
        },
        changeFrequency: "daily",
        priority: 0.6,
      });
      entries.push({
        url: `${BASE_URL}/pt/${ticker}/${ptSlug}`,
        alternates: {
          languages: {
            "pt-BR": `${BASE_URL}/pt/${ticker}/${ptSlug}`,
            en: `${BASE_URL}/en/${ticker}/${enSlug}`,
          },
        },
        changeFrequency: "daily",
        priority: 0.6,
      });
    }
  }

  return entries;
}
