/**
 * `/sitemaps/{file}` · the children named by the index at `/sitemap.xml`.
 *
 * `pages.xml` holds the handful of pages that are not about a company.
 * `companies-{n}.xml` holds one slice of the universe.
 */
import {
  SYMBOLS_PER_SITEMAP,
  buildCompanyEntries,
  buildStaticEntries,
  chunk,
  parseSitemapName,
  renderUrlSet,
} from "../../../lib/sitemap";
import { fetchCompanySymbols, fetchLastModified } from "../../../lib/sitemap-data";

export const runtime = "nodejs";

const ONE_HOUR_IN_SECONDS = 3600;
const ONE_DAY_IN_SECONDS = 86400;

const STATIC_SITEMAP_FILE = "pages.xml";

function xml(body: string): Response {
  return new Response(body, {
    headers: {
      "Content-Type": "application/xml; charset=utf-8",
      "Cache-Control": `public, max-age=${ONE_HOUR_IN_SECONDS}, s-maxage=${ONE_DAY_IN_SECONDS}`,
    },
  });
}

function notFound(): Response {
  return new Response("Not found\n", {
    status: 404,
    headers: { "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store" },
  });
}

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ file: string }> },
) {
  const { file } = await params;

  if (file === STATIC_SITEMAP_FILE) {
    return xml(renderUrlSet(buildStaticEntries(await fetchLastModified())));
  }

  const index = parseSitemapName(file);
  if (index === null) return notFound();

  const [symbols, lastModified] = await Promise.all([
    fetchCompanySymbols(),
    fetchLastModified(),
  ]);

  const batch = chunk(symbols, SYMBOLS_PER_SITEMAP)[index];
  // A chunk past the end of the universe is a stale URL from an older index.
  // 404 rather than serve an empty urlset, which reads as "these pages are
  // gone" to a crawler.
  if (!batch) return notFound();

  return xml(renderUrlSet(buildCompanyEntries(batch, lastModified)));
}
