/**
 * Server-to-server fetches to Django, with one retry on a dead connection.
 *
 * gunicorn's sync workers do not support keep-alive and close the connection
 * on every response. Node's HTTP client intermittently fails to parse that,
 * throwing `HPE_CLOSED_CONNECTION` ("Data after `Connection: close`"). When
 * it happened inside Next's `/api/` proxy the visitor got a 500; nginx now
 * routes `/api/` straight to Django so that path is gone, but Next still
 * calls Django directly for server-rendered pages, the markdown twins, the
 * sitemap and the Open Graph cards, and those calls can still hit it.
 *
 * A second attempt gets a fresh socket and succeeds. One retry, not more:
 * if Django is actually down, hammering it helps nobody, and every caller
 * here degrades gracefully on null.
 */

/** Methods safe to replay. A POST could double-write. */
const IDEMPOTENT_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

/**
 * Fetch, retrying once on a transport failure.
 *
 * Returns the `Response` whatever its status, so the caller still sees a 404
 * or a 429 and can act on it. Returns null only when the request could not be
 * completed at all.
 */
export async function fetchFromDjango(
  url: string,
  init: RequestInit & { next?: { revalidate?: number } } = {},
): Promise<Response | null> {
  const method = (init.method ?? "GET").toUpperCase();
  const attempts = IDEMPOTENT_METHODS.has(method) ? 2 : 1;

  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      return await fetch(url, init);
    } catch {
      // Transport-level failure. Fall through to the retry, or to null.
    }
  }
  return null;
}
