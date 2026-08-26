/**
 * URL shaping for the markdown twin of every public page.
 *
 * Any page at `/{locale}/{path}` is also served as plain markdown at
 * `/{locale}/{path}.md`. That suffix convention is the one Anthropic,
 * Stripe and Mintlify docs use, and it is the point: a model holding an
 * HTML URL can guess the markdown one without being told.
 *
 * Kept free of React, of `next/server`, and of the renderer itself so
 * `middleware.ts` can import it without dragging anything into the edge
 * bundle.
 */
import { DEFAULT_LOCALE, isSupportedLocale } from "./i18n-config";
import { KNOWN_LOCALE_ROUTES, MARKDOWN_LOCALE_ROUTES } from "./site-routes";
import { tabSlugForLocale, type TabKey } from "../utils/tabs";

export const MARKDOWN_EXTENSION = ".md";

/** Internal route the suffix URLs are rewritten onto. */
export const MARKDOWN_ROUTE_PREFIX = "/md";

/**
 * First segments that must never be read as a locale or a ticker.
 *
 * `md` is in the list so a rewritten path cannot be rewritten again, and
 * `og` because an Open Graph card URL ending in `.md` is a malformed image
 * request, not a page.
 */
const RESERVED_FIRST_SEGMENTS = new Set([
  "_next",
  "admin",
  "api",
  "fonts",
  "images",
  "md",
  "og",
  "static",
  "unsubscribe",
]);

/** locale + ticker + tab. Nothing public is deeper than that. */
const MAX_SEGMENTS = 3;

/** Public markdown URL for one company page, in one locale. */
export function markdownUrlFor(locale: string, ticker: string, tab: TabKey = "metrics"): string {
  const slug = tabSlugForLocale(locale, tab);
  const base = slug
    ? `/${locale}/${ticker.toUpperCase()}/${slug}`
    : `/${locale}/${ticker.toUpperCase()}`;
  return `${base}${MARKDOWN_EXTENSION}`;
}

/**
 * The internal path a `.md` request should be rewritten to, or null when
 * the request is not one of ours.
 *
 * Returning null is the common case and must stay cheap: every dotted path
 * on the site reaches this function once the middleware matcher stops
 * excluding them.
 *
 * The locale-versus-ticker call is decided on case alone. Locales are
 * lowercase everywhere in this app and tickers are uppercase, which is what
 * lets `/de.md` be the German home page while `/DE.md` is Deere & Company.
 */
export function markdownRewritePath(pathname: string): string | null {
  if (!pathname.endsWith(MARKDOWN_EXTENSION)) return null;

  const withoutExtension = pathname.slice(0, -MARKDOWN_EXTENSION.length);
  const segments = withoutExtension.split("/").filter(Boolean);
  if (segments.length === 0 || segments.length > MAX_SEGMENTS) return null;
  if (RESERVED_FIRST_SEGMENTS.has(segments[0])) return null;

  if (isSupportedLocale(segments[0])) {
    const [locale, ...rest] = segments;
    const normalized = normalizeAfterLocale(rest);
    if (normalized === null) return null;
    return [MARKDOWN_ROUTE_PREFIX, locale, ...normalized].join("/");
  }

  // No locale prefix. The remaining segment has to be a bare company page,
  // so anything with a tab under it is not a URL we serve.
  if (segments.length > 1 || KNOWN_LOCALE_ROUTES.has(segments[0])) return null;
  return [MARKDOWN_ROUTE_PREFIX, DEFAULT_LOCALE, segments[0].toUpperCase()].join("/");
}

/**
 * Uppercase the ticker segment, leaving the tab slug alone.
 *
 * Returns null for a named route that has no markdown twin, and for the
 * named routes that do, leaves the name as written rather than turning
 * `/en/screener.md` into a company called SCREENER.
 */
function normalizeAfterLocale(segments: string[]): string[] | null {
  if (segments.length === 0) return segments;

  const [first, ...rest] = segments;
  if (KNOWN_LOCALE_ROUTES.has(first)) {
    return MARKDOWN_LOCALE_ROUTES.has(first) && rest.length === 0 ? [first] : null;
  }
  return [first.toUpperCase(), ...rest];
}
