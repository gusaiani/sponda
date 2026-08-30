/**
 * The HTTP shape every Open Graph image on the domain is served in.
 *
 * Two properties matter to social crawlers and are easy to lose:
 *
 * - `Content-Length`. X's crawler sizes an image with a HEAD request before
 *   deciding whether to download it, and messaging apps enforce size caps
 *   the same way. A chunked response answers neither.
 * - No validators (`ETag`, `Last-Modified`, `Accept-Ranges`). A crawler
 *   that holds a bad copy of an image and can revalidate it cheaply never
 *   has to download it again; with nothing to revalidate against, the only
 *   way to have the image is to GET it.
 *
 * Neither was the root cause of X's imageless cards (that was a robots.txt
 * rule, see `public/robots.txt`, and Next's RSC `Vary` header, stripped in
 * `nginx/sponda.capital.conf`), but both remove a way for the next failure
 * to become permanent.
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
