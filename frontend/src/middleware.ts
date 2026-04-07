import { NextRequest, NextResponse } from "next/server";
import { SUPPORTED_LOCALES, DEFAULT_LOCALE, isSupportedLocale, detectLocaleFromHeader } from "./lib/i18n-config";

const DJANGO_API_URL = process.env.DJANGO_API_URL || "http://localhost:8710";

/** Tab slug mappings for cross-locale redirects. */
const PT_TO_EN_SLUG: Record<string, string> = {
  fundamentos: "fundamentals",
  comparar: "compare",
  graficos: "charts",
};
const EN_TO_PT_SLUG: Record<string, string> = {
  fundamentals: "fundamentos",
  compare: "comparar",
  charts: "graficos",
};
const ALL_TAB_SLUGS = new Set([...Object.keys(PT_TO_EN_SLUG), ...Object.keys(EN_TO_PT_SLUG)]);

function isPortugueseTabSlug(slug: string): boolean {
  return slug in PT_TO_EN_SLUG;
}

function isEnglishTabSlug(slug: string): boolean {
  return slug in EN_TO_PT_SLUG;
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // 1. Proxy API, OG images, sitemap, and admin to Django
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

  // 2. Already locale-prefixed: validate and handle cross-locale tab slugs
  const segments = pathname.split("/").filter(Boolean);
  const firstSegment = segments[0];

  if (firstSegment && isSupportedLocale(firstSegment)) {
    const locale = firstSegment;
    // Check if a tab slug needs cross-locale redirect
    // Pattern: /{locale}/{ticker}/{tabSlug}
    if (segments.length === 3) {
      const tabSlug = segments[2];
      if (ALL_TAB_SLUGS.has(tabSlug)) {
        if (locale === "en" && isPortugueseTabSlug(tabSlug)) {
          // /en/PETR4/fundamentos → /en/PETR4/fundamentals
          const correctSlug = PT_TO_EN_SLUG[tabSlug];
          const url = request.nextUrl.clone();
          url.pathname = `/${locale}/${segments[1]}/${correctSlug}`;
          return NextResponse.redirect(url, 301);
        }
        if (locale === "pt" && isEnglishTabSlug(tabSlug)) {
          // /pt/PETR4/fundamentals → /pt/PETR4/fundamentos
          const correctSlug = EN_TO_PT_SLUG[tabSlug];
          const url = request.nextUrl.clone();
          url.pathname = `/${locale}/${segments[1]}/${correctSlug}`;
          return NextResponse.redirect(url, 301);
        }
      }
    }

    // Valid locale prefix — pass through
    return NextResponse.next();
  }

  // 3. Bare URL → redirect to locale-prefixed version
  const locale = detectLocaleFromHeader(request.headers.get("accept-language"));

  // Translate tab slugs when redirecting to a different locale
  let newPathname = pathname;
  if (segments.length >= 2) {
    const lastSegment = segments[segments.length - 1];
    if (locale === "en" && isPortugueseTabSlug(lastSegment)) {
      segments[segments.length - 1] = PT_TO_EN_SLUG[lastSegment];
      newPathname = "/" + segments.join("/");
    } else if (locale === "pt" && isEnglishTabSlug(lastSegment)) {
      segments[segments.length - 1] = EN_TO_PT_SLUG[lastSegment];
      newPathname = "/" + segments.join("/");
    }
  }

  const url = request.nextUrl.clone();
  url.pathname = `/${locale}${newPathname === "/" ? "" : newPathname}`;
  return NextResponse.redirect(url, 301);
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|images|fonts|favicon|.*\\..*).*)"],
};
