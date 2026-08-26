import { NextRequest, NextResponse } from "next/server";
import { isSupportedLocale, detectLocaleFromHeader } from "./lib/i18n-config";
import { MARKDOWN_EXTENSION, markdownRewritePath } from "./lib/markdown-routes";
import { KNOWN_LOCALE_ROUTES } from "./lib/site-routes";

const DJANGO_API_URL = process.env.DJANGO_API_URL || "http://localhost:8710";

/** Kept in step with `src/app/md/[...slug]/route.ts`. */
const MARKDOWN_CONTENT_TYPE = "text/markdown; charset=utf-8";
export const LANGUAGE_COOKIE_NAME = "sponda-lang";
const LANGUAGE_COOKIE_MAX_AGE = 365 * 24 * 60 * 60;

function persistLocaleCookie(response: NextResponse, locale: string): NextResponse {
  response.cookies.set(LANGUAGE_COOKIE_NAME, locale, {
    path: "/",
    maxAge: LANGUAGE_COOKIE_MAX_AGE,
    sameSite: "lax",
  });
  return response;
}

/**
 * Canonical (English) tab slug for every known locale-specific slug.
 * Used to detect cross-locale tab slugs and redirect to the correct one.
 */
const SLUG_TO_CANONICAL: Record<string, string> = {
  /* English (canonical) */
  charts: "charts",
  fundamentals: "fundamentals",
  compare: "compare",
  /* Portuguese / Spanish (shared slugs) */
  graficos: "charts",
  fundamentos: "fundamentals",
  comparar: "compare",
  /* French */
  graphiques: "charts",
  fondamentaux: "fundamentals",
  comparer: "compare",
  /* German */
  diagramme: "charts",
  fundamentaldaten: "fundamentals",
  vergleich: "compare",
  /* Italian */
  grafici: "charts",
  fondamentali: "fundamentals",
  confronta: "compare",
};

/** Locale → { canonical → localized slug } */
const CANONICAL_TO_LOCALE_SLUG: Record<string, Record<string, string>> = {
  pt: { charts: "graficos", fundamentals: "fundamentos", compare: "comparar" },
  en: { charts: "charts", fundamentals: "fundamentals", compare: "compare" },
  es: { charts: "graficos", fundamentals: "fundamentos", compare: "comparar" },
  zh: { charts: "charts", fundamentals: "fundamentals", compare: "compare" },
  fr: { charts: "graphiques", fundamentals: "fondamentaux", compare: "comparer" },
  de: { charts: "diagramme", fundamentals: "fundamentaldaten", compare: "vergleich" },
  it: { charts: "grafici", fundamentals: "fondamentali", compare: "confronta" },
};

function correctSlugForLocale(locale: string, slug: string): string | null {
  const canonical = SLUG_TO_CANONICAL[slug];
  if (!canonical) return null;
  const expected = CANONICAL_TO_LOCALE_SLUG[locale]?.[canonical];
  if (!expected || expected === slug) return null;
  return expected;
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // 1. Google OAuth callback — locale-free, served by Next.js (not Django)
  if (pathname.startsWith("/google/callback")) {
    return NextResponse.next();
  }

  // 2. Per-company Open Graph cards are rendered by Next itself, at
  // src/app/og/[locale]/[ticker]/route.tsx. Let them through untouched: the
  // locale is already a path segment, and a crawler impatient about an image
  // should not pay for a redirect. Django has no /og/ routes — it used to
  // answer here with the legacy SPA shell, HTML with a 200 status, which is
  // worse than a 404 for a crawler that asked for an image.
  if (pathname.startsWith("/og/")) {
    return NextResponse.next();
  }

  // 3. Proxy API, sitemap, admin, and the email opt-out page to Django.
  // /static/ is Django's static files (the admin's stylesheets), served by
  // WhiteNoise. /unsubscribe/ is locale-free on purpose: the link sits in
  // an inbox forever, so it must never be rewritten, uppercased, or
  // locale-prefixed — the signed token is part of the path.
  if (
    pathname.startsWith("/api/") ||
    pathname.startsWith("/admin/") ||
    pathname.startsWith("/static/") ||
    pathname.startsWith("/unsubscribe/")
  ) {
    const target = new URL(pathname + request.nextUrl.search, DJANGO_API_URL);
    const headers = new Headers(request.headers);
    headers.set("Host", new URL(DJANGO_API_URL).host);
    return NextResponse.rewrite(target, { request: { headers } });
  }

  // 4. Markdown twin of a public page: /en/PETR4.md -> /md/en/PETR4.
  // Handled here rather than through a next.config rewrite because all the
  // other URL shaping lives in this file, because path-to-regexp's treatment
  // of a ".md" literal after a greedy :param is the kind of thing that fails
  // silently in production, and because this file has a test harness.
  //
  // The rewrite deliberately never redirects: a crawler that guessed the URL
  // from an HTML link should get the document, not a hop into a locale it did
  // not ask for. Ticker case is fixed in place instead.
  if (pathname.endsWith(MARKDOWN_EXTENSION)) {
    const markdownPath = markdownRewritePath(pathname);
    if (!markdownPath) {
      // A .md URL we do not publish, such as /en/login.md. Answer 404 here
      // rather than fall through: the ticker-case rule below would redirect
      // it to /en/LOGIN.MD, and `[locale]/[ticker]` would then answer that
      // with a 200 HTML shell. We own the .md namespace, so an unknown one
      // is a miss and should say so.
      return new NextResponse("Not found\n", {
        status: 404,
        headers: {
          "Content-Type": MARKDOWN_CONTENT_TYPE,
          "Cache-Control": "no-store",
        },
      });
    }
    const url = request.nextUrl.clone();
    url.pathname = markdownPath;
    return NextResponse.rewrite(url);
  }

  // 5. Already locale-prefixed: validate and handle cross-locale tab slugs
  const segments = pathname.split("/").filter(Boolean);
  const firstSegment = segments[0];

  if (firstSegment && isSupportedLocale(firstSegment)) {
    const locale = firstSegment;

    // Normalize ticker case: /en/petr4 → /en/PETR4. Uses 302 (not 301)
    // so browsers don't permanently cache the redirect. Adding a new
    // entry to KNOWN_LOCALE_ROUTES (e.g. /user, /spond) used to poison
    // browser caches forever — every previous visitor to /pt/user/x had
    // it cached as a 301 to /pt/USER/x and would never reach the new
    // route. With 302, the next refresh re-checks with the server.
    if (segments.length >= 2 && !KNOWN_LOCALE_ROUTES.has(segments[1])) {
      const tickerSegment = segments[1];
      const upperTicker = tickerSegment.toUpperCase();
      if (tickerSegment !== upperTicker) {
        const url = request.nextUrl.clone();
        segments[1] = upperTicker;
        url.pathname = `/${segments.join("/")}`;
        return persistLocaleCookie(NextResponse.redirect(url, 302), locale);
      }
    }

    // Check if a tab slug needs cross-locale redirect
    // Pattern: /{locale}/{ticker}/{tabSlug}
    if (segments.length === 3) {
      const tabSlug = segments[2];
      const corrected = correctSlugForLocale(locale, tabSlug);
      if (corrected) {
        const url = request.nextUrl.clone();
        url.pathname = `/${locale}/${segments[1]}/${corrected}`;
        return persistLocaleCookie(NextResponse.redirect(url, 302), locale);
      }
    }

    // Valid locale prefix — pass through, persist cookie so bare visits keep it
    return persistLocaleCookie(NextResponse.next(), locale);
  }

  // 6. Bare URL → redirect to locale-prefixed version
  // Priority: cookie (user's explicit choice) → Accept-Language → default
  const cookieLocale = request.cookies.get("sponda-lang")?.value;
  const locale = (cookieLocale && isSupportedLocale(cookieLocale))
    ? cookieLocale
    : detectLocaleFromHeader(request.headers.get("accept-language"));

  // Normalize ticker case and translate tab slugs when redirecting
  let newPathname = pathname;
  if (segments.length >= 1 && !KNOWN_LOCALE_ROUTES.has(segments[0])) {
    segments[0] = segments[0].toUpperCase();
  }
  if (segments.length >= 2) {
    const lastSegment = segments[segments.length - 1];
    const corrected = correctSlugForLocale(locale, lastSegment);
    if (corrected) {
      segments[segments.length - 1] = corrected;
    }
  }
  if (segments.length >= 1) {
    newPathname = "/" + segments.join("/");
  }

  const url = request.nextUrl.clone();
  url.pathname = `/${locale}${newPathname === "/" ? "" : newPathname}`;
  // 302 (not 301) because the chosen locale depends on per-request signals
  // (sponda-lang cookie, Accept-Language). A 301 would be cached by browsers
  // indefinitely and ignore future cookie/header changes.
  const response = NextResponse.redirect(url, 302);
  response.headers.set("Cache-Control", "no-store");
  response.headers.set("Vary", "Cookie, Accept-Language");
  return persistLocaleCookie(response, locale);
}

export const config = {
  // Ordering matters: the explicit `/api/`, `/og/`, and `/admin/` matchers
  // must come before the catch-all, because the catch-all excludes any path
  // containing a dot — which would otherwise skip logo requests like
  // `/api/logos/PETR4.png`.
  matcher: [
    "/api/((?!assistant/ask).*)",
    "/og/:path*",
    "/admin/:path*",
    // Django's static files (admin css) — explicit, because the filenames
    // contain dots and the catch-all below skips any path that does.
    "/static/:path*",
    // Explicit, because a signed unsubscribe token can contain a dot and the
    // catch-all below skips any path that does.
    "/unsubscribe/:path*",
    // The markdown twin of every public page. Explicit, because the
    // catch-all below skips any path that contains a dot and would
    // otherwise let every .md URL fall through to a 404. The negative
    // lookahead keeps this from stealing paths the entries above own.
    "/((?!_next|api|og|admin|static|unsubscribe|images|fonts).*\\.md)",
    "/((?!_next|images|fonts|favicon|api/assistant/ask|.*\\..*).*)",
  ],
};
