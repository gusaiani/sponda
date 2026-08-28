/**
 * `/{locale}/{page}.md` · the markdown twin of every public page.
 *
 * `middleware.ts` rewrites the suffix URLs onto this handler, so the shapes
 * that arrive here are `/md/{locale}`, `/md/{locale}/screener`,
 * `/md/{locale}/{TICKER}` and `/md/{locale}/{TICKER}/{tabSlug}`.
 *
 * Modelled on `src/app/og/[locale]/[ticker]/route.tsx`, which renders the
 * same company data on demand into a different format and caches it the same
 * way. Every fetch behind this handler is DB-only on the Django side; none of
 * them can trigger a provider call or count against the daily lookup cap.
 */
import {
  buildCompanyMarkdownModel,
  fetchCompanyMarkdownData,
  renderCompanyMarkdown,
} from "../../../lib/company-markdown";
import {
  fetchIndicatorCatalogue,
  renderAiAccessMarkdown,
  renderHomeMarkdown,
  renderScreenerMarkdown,
} from "../../../lib/site-markdown";
import { isSupportedLocale, type SupportedLocale } from "../../../lib/i18n-config";
import { MARKDOWN_LOCALE_ROUTES, SITE_BASE_URL } from "../../../lib/site-routes";
import { resolveTab, tabSlugForLocale, type TabKey } from "../../../utils/tabs";

export const runtime = "nodejs";

const MARKDOWN_CONTENT_TYPE = "text/markdown; charset=utf-8";

const ONE_HOUR_IN_SECONDS = 3600;
const FIFTEEN_MINUTES_IN_SECONDS = 900;
const ONE_DAY_IN_SECONDS = 86400;
const ONE_WEEK_IN_SECONDS = 604800;

/** locale + ticker + tab, matching what the rewrite can produce. */
const MAX_SLUG_SEGMENTS = 3;

/**
 * Fresh at the browser for as long as the snapshot itself is, cached far
 * longer at the edge, and served stale for a week while it revalidates.
 *
 * The same shape `cardCacheControl()` uses for Open Graph cards. Note that
 * `.md` is not in Cloudflare's default cacheable-extension list: without a
 * Cache Rule matching `*.md`, this header is honoured by browsers only and
 * every request reaches the origin.
 */
function markdownCacheControl(maxAge: number): string {
  return [
    "public",
    `max-age=${maxAge}`,
    `s-maxage=${ONE_DAY_IN_SECONDS}`,
    `stale-while-revalidate=${ONE_WEEK_IN_SECONDS}`,
  ].join(", ");
}

/**
 * `Link: <html page>; rel="canonical"`.
 *
 * The markdown is a twin, not a page of its own. Every HTML page advertises
 * it through `<link rel="alternate" type="text/markdown">`, so a search
 * crawler will find these URLs, and text/markdown is indexable. Without a
 * canonical, Google would hold two documents per company and pick one, and
 * the markdown is the likelier pick because it carries the numbers the HTML
 * does not. A header rather than anything in the body: markdown has no head,
 * and this keeps the document itself clean for the models that read it.
 */
function canonicalLink(pagePath: string): string {
  return `<${SITE_BASE_URL}${pagePath}>; rel="canonical"`;
}

function markdown(body: string, maxAge: number, canonicalPagePath: string): Response {
  return new Response(body, {
    headers: {
      "Content-Type": MARKDOWN_CONTENT_TYPE,
      "Cache-Control": markdownCacheControl(maxAge),
      Link: canonicalLink(canonicalPagePath),
    },
  });
}

/** A 404 must never be cached: a ticker we do not know today we may know
 * tomorrow, and Cloudflare would otherwise pin the miss for hours. */
function notFound(): Response {
  return new Response("Not found\n", {
    status: 404,
    headers: { "Content-Type": MARKDOWN_CONTENT_TYPE, "Cache-Control": "no-store" },
  });
}

/**
 * The tab a slug names, or null when the slug is unknown or belongs to
 * another locale.
 *
 * Rejecting a cross-locale slug matters here in a way it does not on the
 * HTML side: `[...tab]/page.tsx` can rely on the middleware having already
 * redirected `/en/PETR4/graficos`, but nothing redirects `.md` URLs, so one
 * company would otherwise answer on several URLs per tab.
 */
function tabFromSlug(locale: SupportedLocale, slug: string): TabKey | null {
  const tab = resolveTab(`/${locale}/X/${slug}`);
  if (tab === "metrics") return null;
  return tabSlugForLocale(locale, tab) === slug ? tab : null;
}

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ slug: string[] }> },
) {
  const { slug } = await params;
  if (!slug || slug.length === 0 || slug.length > MAX_SLUG_SEGMENTS) return notFound();

  const [locale, second, third] = slug;
  if (!isSupportedLocale(locale)) return notFound();

  if (second === undefined) {
    return markdown(renderHomeMarkdown(locale), ONE_HOUR_IN_SECONDS, `/${locale}`);
  }

  if (MARKDOWN_LOCALE_ROUTES.has(second)) {
    if (third !== undefined) return notFound();
    if (second === "for-ai") {
      return markdown(renderAiAccessMarkdown(locale), ONE_HOUR_IN_SECONDS, `/${locale}/${second}`);
    }
    return markdown(
      renderScreenerMarkdown(locale, await fetchIndicatorCatalogue()),
      ONE_HOUR_IN_SECONDS,
      `/${locale}/${second}`,
    );
  }

  const ticker = second.toUpperCase();
  let tab: TabKey = "metrics";
  if (third !== undefined) {
    const resolved = tabFromSlug(locale, third);
    if (resolved === null) return notFound();
    tab = resolved;
  }

  const data = await fetchCompanyMarkdownData(ticker, tab);
  if (!data.snapshot) return notFound();

  const companyPagePath = third === undefined ? `/${locale}/${ticker}` : `/${locale}/${ticker}/${third}`;
  return markdown(
    renderCompanyMarkdown(buildCompanyMarkdownModel({ ticker, locale, tab, data })),
    FIFTEEN_MINUTES_IN_SECONDS,
    companyPagePath,
  );
}
