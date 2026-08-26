/**
 * `/sitemap.xml` · a sitemap index, not the sitemap itself.
 *
 * What this replaces listed about 155 curated symbols, under 1% of the
 * catalogue, so nothing pointed crawlers at the other 18,000 companies or at
 * their markdown twins.
 *
 * Replaces the `app/sitemap.ts` file convention, which cannot express an
 * index whose children are generated on demand.
 */
import {
  SYMBOLS_PER_SITEMAP,
  chunk,
  companySitemapName,
  renderSitemapIndex,
} from "../../lib/sitemap";
import { fetchCompanySymbols, fetchLastModified } from "../../lib/sitemap-data";
import { SITE_BASE_URL } from "../../lib/site-routes";

export const runtime = "nodejs";

/**
 * Rendered per request, never prerendered.
 *
 * The symbol list comes from Django, which is not reachable from the CI
 * runner where `next build` happens. Left static, the build would bake an
 * index naming no company sitemaps at all and serve that until the first
 * revalidation. The underlying fetches are still cached for an hour, so the
 * cost of being dynamic is one Redis-backed call.
 */
export const dynamic = "force-dynamic";

const ONE_HOUR_IN_SECONDS = 3600;
const ONE_DAY_IN_SECONDS = 86400;

export async function GET(): Promise<Response> {
  const [symbols, lastModified] = await Promise.all([
    fetchCompanySymbols(),
    fetchLastModified(),
  ]);

  const children = [`${SITE_BASE_URL}/sitemaps/pages.xml`];
  chunk(symbols, SYMBOLS_PER_SITEMAP).forEach((_batch, index) => {
    children.push(`${SITE_BASE_URL}/sitemaps/${companySitemapName(index)}`);
  });

  return new Response(renderSitemapIndex(children, lastModified), {
    headers: {
      "Content-Type": "application/xml; charset=utf-8",
      "Cache-Control": `public, max-age=${ONE_HOUR_IN_SECONDS}, s-maxage=${ONE_DAY_IN_SECONDS}`,
    },
  });
}
