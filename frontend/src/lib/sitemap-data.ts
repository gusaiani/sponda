/**
 * The two things the sitemap routes need from Django: the symbol list and a
 * last-modified date. Shared so the index and its children agree on both.
 */
import { djangoApiBaseUrl } from "./django-api";

/** The universe changes when tickers are onboarded, which is not often. */
const SYMBOLS_REVALIDATE_SECONDS = 3600;

/** Matches the cadence the previous sitemap used for its lastmod probe. */
const HEALTH_REVALIDATE_SECONDS = 900;

/**
 * Every listed company symbol.
 *
 * Returns an empty list rather than throwing: a sitemap index that still
 * names the static pages beats a 500, because a 500 is what a crawler
 * remembers.
 */
export async function fetchCompanySymbols(): Promise<string[]> {
  try {
    const response = await fetch(`${djangoApiBaseUrl()}/api/tickers/symbols/`, {
      next: { revalidate: SYMBOLS_REVALIDATE_SECONDS },
    });
    if (!response.ok) return [];
    const payload = (await response.json()) as { symbols?: string[] };
    return payload.symbols ?? [];
  } catch {
    return [];
  }
}

/** When the ticker data last changed, for `<lastmod>`. */
export async function fetchLastModified(): Promise<string> {
  try {
    const response = await fetch(`${djangoApiBaseUrl()}/api/health/`, {
      next: { revalidate: HEALTH_REVALIDATE_SECONDS },
    });
    if (response.ok) {
      const payload = await response.json();
      if (payload?.tickers?.last_updated) return payload.tickers.last_updated as string;
    }
  } catch {
    // fall through
  }
  return new Date().toISOString();
}
