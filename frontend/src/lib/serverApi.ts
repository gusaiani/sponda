/**
 * Server-only fetch helpers for prefetching Django data inside Server
 * Components. Forwards the user's session cookie so authenticated
 * endpoints (favorites, saved lists) work without re-authentication.
 *
 * Use only in Server Components / Route Handlers — calling this on the
 * client throws.
 */
import "server-only";

import { cookies } from "next/headers";

const DJANGO_API_URL = process.env.DJANGO_API_URL || "http://localhost:8710";

interface ServerFetchOptions extends RequestInit {
  /** Skip cookie forwarding (anonymous fetch). Default: false. */
  anonymous?: boolean;
}

export async function serverFetch(
  pathname: string,
  options: ServerFetchOptions = {},
): Promise<Response> {
  const { anonymous, headers, ...rest } = options;
  const target = new URL(pathname, DJANGO_API_URL);

  const requestHeaders = new Headers(headers);
  if (!anonymous) {
    const cookieStore = await cookies();
    const cookieHeader = cookieStore
      .getAll()
      .map((cookie) => `${cookie.name}=${cookie.value}`)
      .join("; ");
    if (cookieHeader) {
      requestHeaders.set("Cookie", cookieHeader);
    }
  }

  return fetch(target, {
    ...rest,
    headers: requestHeaders,
    // SSR pre-fetch: data is per-user, never share between requests.
    cache: "no-store",
  });
}

export async function serverFetchJSON<T>(
  pathname: string,
  options: ServerFetchOptions = {},
  fallback: T,
): Promise<T> {
  try {
    const response = await serverFetch(pathname, options);
    if (!response.ok) return fallback;
    return (await response.json()) as T;
  } catch {
    return fallback;
  }
}
