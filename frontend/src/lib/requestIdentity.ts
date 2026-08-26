/**
 * Who a server-side call into Django is on behalf of.
 *
 * A Server Component that fetches from Django opens a fresh connection out
 * of the Node process, so Django sees `127.0.0.1` and no session unless we
 * say otherwise. That is not cosmetic: the daily company-lookup cap is
 * scoped by hashed client IP, so every server-rendered quote on the site
 * shared a single anonymous bucket of twenty tickers a day. Past the
 * twentieth, `PE10View` answered 429 and the ticker page server-rendered an
 * empty skeleton: no company for a crawler to read, and a first client
 * render that disagreed with it (JAVASCRIPT-NEXTJS-2).
 *
 * Forwarding the visitor's cookies and client address puts the call back on
 * the visitor's own quota, which is where a page view belongs.
 */
import { headers } from "next/headers";

/**
 * Client-address headers, in the order `quotes.client_ip.client_ip` reads
 * them. nginx sets both, from a `$remote_addr` the realip module resolves
 * from `CF-Connecting-IP` only for connections arriving from a published
 * Cloudflare range. That gating is what makes them safe to forward: whatever
 * the original caller sent has already been overwritten by the time this code
 * sees it. See "Origin trust" in the README.
 */
const CLIENT_ADDRESS_HEADERS = ["cf-connecting-ip", "x-forwarded-for"] as const;

/**
 * Build the headers that identify the current visitor to Django.
 *
 * Call this outside any `try`: `headers()` is how Next.js learns the render
 * is dynamic, and swallowing that signal would let a ticker page be
 * prerendered with one visitor's session.
 */
export async function requestIdentityHeaders(): Promise<Headers> {
  const incomingHeaders = await headers();
  const identityHeaders = new Headers();

  const cookieHeader = incomingHeaders.get("cookie");
  if (cookieHeader) {
    identityHeaders.set("cookie", cookieHeader);
  }

  for (const headerName of CLIENT_ADDRESS_HEADERS) {
    const clientAddress = incomingHeaders.get(headerName);
    if (clientAddress) {
      identityHeaders.set(headerName, clientAddress);
    }
  }

  return identityHeaders;
}
