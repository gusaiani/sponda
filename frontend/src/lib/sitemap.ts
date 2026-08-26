/**
 * Sitemap generation for the whole company universe.
 *
 * What this replaces covered about 1% of the catalogue. `app/sitemap.ts`
 * enumerated `CURATED_TICKERS`, roughly 155 hand-picked symbols, while
 * Django's `SitemapView` did enumerate everything but built 600k `<url>`
 * entries in a single uncompressed document, past the 50,000-URL limit, and
 * was unreachable anyway because `/sitemap.xml` contains a dot and Next's
 * middleware skips dotted paths.
 *
 * So: a sitemap index at `/sitemap.xml` pointing at paginated children under
 * `/sitemaps/`. The XML is written out by hand rather than through Next's
 * `MetadataRoute.Sitemap` convention, because the convention has no way to
 * express an index whose children are generated on demand.
 */
import { INDEXABLE_LOCALES, type SupportedLocale } from "./i18n-config";
import { SITE_BASE_URL } from "./site-routes";
import { tabSlugForLocale, type TabKey } from "../utils/tabs";

/**
 * URLs per child sitemap.
 *
 * The protocol ceiling is 50,000 URLs or 50MB uncompressed, whichever comes
 * first. Every entry here carries up to six `xhtml:link` alternates, so bytes
 * per URL run several times a bare `<loc>` and 50,000 entries would crowd the
 * size limit. 20,000 keeps both bounds comfortable.
 */
export const MAX_URLS_PER_SITEMAP = 20_000;

/**
 * Locales that get their own `<url>` entry.
 *
 * Every indexable locale is still advertised as an `hreflang` alternate on
 * each entry, which is how Google is told the other five exist. Emitting a
 * separate entry per locale as well would multiply the document by three for
 * no additional discovery.
 */
export const SITEMAP_LOCALES: SupportedLocale[] = ["en", "pt"];

/** Company pages worth listing. `metrics` is the company root, with no slug. */
const COMPANY_TABS: TabKey[] = ["metrics", "charts", "fundamentals", "compare"];

/**
 * Symbols per child sitemap, once every page and locale is counted.
 *
 * Lives here rather than in the route so the index and the children derive it
 * from one place. If they ever disagreed, the index would advertise children
 * that 404 or omit ones that exist.
 */
export const SYMBOLS_PER_SITEMAP = Math.floor(
  MAX_URLS_PER_SITEMAP / (COMPANY_TABS.length * SITEMAP_LOCALES.length),
);

const COMPANY_SITEMAP_PREFIX = "companies-";
const SITEMAP_EXTENSION = ".xml";

export interface SitemapEntry {
  url: string;
  lastModified?: string;
  changeFrequency?: "always" | "hourly" | "daily" | "weekly" | "monthly" | "yearly" | "never";
  priority?: number;
  alternates?: { languages: Record<string, string> };
}

export function chunk<T>(items: T[], size: number): T[][] {
  const chunks: T[][] = [];
  for (let index = 0; index < items.length; index += size) {
    chunks.push(items.slice(index, index + size));
  }
  return chunks;
}

export function companySitemapName(index: number): string {
  return `${COMPANY_SITEMAP_PREFIX}${index}${SITEMAP_EXTENSION}`;
}

/**
 * The chunk index a child sitemap filename refers to, or null.
 *
 * Strict on purpose: this value indexes into a slice of the symbol list, and
 * the filename arrives from the URL.
 */
export function parseSitemapName(name: string): number | null {
  if (!name.startsWith(COMPANY_SITEMAP_PREFIX) || !name.endsWith(SITEMAP_EXTENSION)) {
    return null;
  }
  const digits = name.slice(COMPANY_SITEMAP_PREFIX.length, -SITEMAP_EXTENSION.length);
  if (!/^\d+$/.test(digits)) return null;
  return Number(digits);
}

/** hreflang key for a locale. Google wants `pt-BR`, not `pt`, for Brazil. */
function hreflangKey(locale: SupportedLocale): string {
  return locale === "pt" ? "pt-BR" : locale;
}

function companyPath(locale: string, symbol: string, tab: TabKey): string {
  const slug = tabSlugForLocale(locale, tab);
  return slug ? `/${locale}/${symbol}/${slug}` : `/${locale}/${symbol}`;
}

function alternatesFor(pathFor: (locale: SupportedLocale) => string) {
  const languages: Record<string, string> = {};
  for (const locale of INDEXABLE_LOCALES) {
    languages[hreflangKey(locale)] = `${SITE_BASE_URL}${pathFor(locale)}`;
  }
  languages["x-default"] = languages["en"];
  return { languages };
}

/** The company root ranks above its tabs, which are detail views of it. */
function priorityFor(tab: TabKey): number {
  return tab === "metrics" ? 0.8 : 0.6;
}

export function buildCompanyEntries(symbols: string[], lastModified: string): SitemapEntry[] {
  const entries: SitemapEntry[] = [];
  for (const symbol of symbols) {
    for (const tab of COMPANY_TABS) {
      for (const locale of SITEMAP_LOCALES) {
        entries.push({
          url: `${SITE_BASE_URL}${companyPath(locale, symbol, tab)}`,
          lastModified,
          changeFrequency: "daily",
          priority: priorityFor(tab),
          alternates: alternatesFor((alt) => companyPath(alt, symbol, tab)),
        });
      }
    }
  }
  return entries;
}

/**
 * Pages that are not about one company.
 *
 * Auth, account and social routes are deliberately absent: robots.txt
 * disallows them and the social pages additionally emit `noindex`.
 */
export function buildStaticEntries(lastModified: string): SitemapEntry[] {
  const pages: { path: (locale: string) => string; priority: number }[] = [
    { path: (locale) => `/${locale}`, priority: 1 },
    { path: (locale) => `/${locale}/screener`, priority: 0.9 },
  ];

  return pages.flatMap(({ path, priority }) =>
    SITEMAP_LOCALES.map((locale) => ({
      url: `${SITE_BASE_URL}${path(locale)}`,
      lastModified,
      changeFrequency: "daily" as const,
      priority,
      alternates: alternatesFor((alt) => path(alt)),
    })),
  );
}

/** XML text escaping. A symbol with an ampersand would otherwise break the file. */
function escapeXml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

function renderEntry(entry: SitemapEntry): string {
  const lines = [`    <loc>${escapeXml(entry.url)}</loc>`];
  if (entry.lastModified) lines.push(`    <lastmod>${escapeXml(entry.lastModified)}</lastmod>`);
  if (entry.changeFrequency) lines.push(`    <changefreq>${entry.changeFrequency}</changefreq>`);
  if (entry.priority !== undefined) lines.push(`    <priority>${entry.priority}</priority>`);
  for (const [language, href] of Object.entries(entry.alternates?.languages ?? {})) {
    lines.push(
      `    <xhtml:link rel="alternate" hreflang="${escapeXml(language)}" href="${escapeXml(href)}"/>`,
    );
  }
  return `  <url>\n${lines.join("\n")}\n  </url>`;
}

export function renderUrlSet(entries: SitemapEntry[]): string {
  return [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"',
    '        xmlns:xhtml="http://www.w3.org/1999/xhtml">',
    ...entries.map(renderEntry),
    "</urlset>",
    "",
  ].join("\n");
}

export function renderSitemapIndex(childUrls: string[], lastModified: string): string {
  return [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ...childUrls.map((url) => [
      "  <sitemap>",
      `    <loc>${escapeXml(url)}</loc>`,
      `    <lastmod>${escapeXml(lastModified)}</lastmod>`,
      "  </sitemap>",
    ].join("\n")),
    "</sitemapindex>",
    "",
  ].join("\n");
}
