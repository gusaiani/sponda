/**
 * The HTTP shape every Open Graph image on the domain is served in.
 *
 * Two properties matter to social crawlers and are easy to lose:
 *
 * - `Content-Length`. X's crawler sizes an image with a HEAD request before
 *   deciding whether to download it, and messaging apps enforce size caps
 *   the same way. A chunked response answers neither.
 * - No validators (`ETag`, `Last-Modified`, `Accept-Ranges`). X's crawler
 *   kept re-validating the static homepage JPEG with HEAD requests, roughly
 *   twenty a day, without ever downloading it again, while rendering every
 *   card imageless. With nothing to revalidate against, a crawler that wants
 *   the image has to GET it, which is the one thing it did reliably for the
 *   per-company cards.
 */

const ONE_HOUR_IN_SECONDS = 3600;
const ONE_DAY_IN_SECONDS = 86400;
const ONE_WEEK_IN_SECONDS = 604800;

export const OG_IMAGE_CACHE_CONTROL = [
  "public",
  `max-age=${ONE_HOUR_IN_SECONDS}`,
  `s-maxage=${ONE_DAY_IN_SECONDS}`,
  `stale-while-revalidate=${ONE_WEEK_IN_SECONDS}`,
].join(", ");

export function buildOgImageResponse(bytes: Uint8Array, contentType: string): Response {
  return new Response(bytes, {
    status: 200,
    headers: {
      "Content-Type": contentType,
      "Content-Length": String(bytes.byteLength),
      "Cache-Control": OG_IMAGE_CACHE_CONTROL,
    },
  });
}
