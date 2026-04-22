import { getPopularSymbols } from "../utils/suggestedCompanies";

export const BASE_URL = "https://sponda.capital";
const DJANGO_API_URL = process.env.DJANGO_API_URL || "http://localhost:8710";

export const TICKERS_PER_SITEMAP = 1500;

export const FEATURED_TICKERS = [...new Set([
  ...getPopularSymbols("brazil"),
  ...getPopularSymbols("us"),
  ...getPopularSymbols("europe"),
  ...getPopularSymbols("asia"),
])];

export const FEATURED_SET = new Set(FEATURED_TICKERS);

interface TickerEntry {
  symbol: string;
}

export async function fetchAllTickers(): Promise<string[]> {
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

export async function computeSitemapIds(): Promise<{ id: number }[]> {
  const allTickers = await fetchAllTickers();
  const remainingTickers = allTickers.filter((ticker) => !FEATURED_SET.has(ticker));
  const apiChunks = Math.ceil(remainingTickers.length / TICKERS_PER_SITEMAP);

  const ids = [{ id: 0 }, { id: 1 }];
  for (let i = 0; i < apiChunks; i++) {
    ids.push({ id: i + 2 });
  }
  return ids;
}
