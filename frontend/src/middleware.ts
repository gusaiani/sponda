import { NextRequest, NextResponse } from "next/server";
import { SUPPORTED_LOCALES, DEFAULT_LOCALE, isSupportedLocale, detectLocaleFromHeader } from "./lib/i18n-config";

const DJANGO_API_URL = process.env.DJANGO_API_URL || "http://localhost:8710";

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

  // 2. Proxy API, OG images, sitemap, and admin to Django
  if (
    pathname.startsWith("/api/") ||
    pathname.startsWith("/og/") ||
    pathname.startsWith("/admin/")
  ) {
    const target = new URL(pathname + request.nextUrl.search, DJANGO_API_URL);
    const headers = new Headers(request.headers);
    headers.set("Host", new URL(DJANGO_API_URL).host);
    return NextResponse.rewrite(target, { request: { headers } });
  }

  // 3. Already locale-prefixed: validate and handle cross-locale tab slugs
  const segments = pathname.split("/").filter(Boolean);
  const firstSegment = segments[0];

  if (firstSegment && isSupportedLocale(firstSegment)) {
    const locale = firstSegment;
    // Check if a tab slug needs cross-locale redirect
    // Pattern: /{locale}/{ticker}/{tabSlug}
    if (segments.length === 3) {
      const tabSlug = segments[2];
      const corrected = correctSlugForLocale(locale, tabSlug);
      if (corrected) {
        const url = request.nextUrl.clone();
        url.pathname = `/${locale}/${segments[1]}/${corrected}`;
        return NextResponse.redirect(url, 301);
      }
    }

    // Valid locale prefix — pass through
    return NextResponse.next();
  }

  // 4. Bare URL → redirect to locale-prefixed version
  // Priority: saved cookie preference > Accept-Language header > default
  const cookieLocale = request.cookies.get("sponda-lang")?.value;
  const locale = (cookieLocale && isSupportedLocale(cookieLocale))
    ? cookieLocale
    : detectLocaleFromHeader(request.headers.get("accept-language"));

  // Translate tab slugs when redirecting to a different locale
  let newPathname = pathname;
  if (segments.length >= 2) {
    const lastSegment = segments[segments.length - 1];
    const corrected = correctSlugForLocale(locale, lastSegment);
    if (corrected) {
      segments[segments.length - 1] = corrected;
      newPathname = "/" + segments.join("/");
    }
  }

  const url = request.nextUrl.clone();
  url.pathname = `/${locale}${newPathname === "/" ? "" : newPathname}`;
  return NextResponse.redirect(url, 301);
}

export const config = {
  matcher: ["/((?!_next|images|fonts|favicon|.*\\..*).*)"],
};
