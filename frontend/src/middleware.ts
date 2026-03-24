import { NextRequest, NextResponse } from "next/server";

const DJANGO_API_URL = process.env.DJANGO_API_URL || "http://localhost:8710";

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Proxy API, OG images, sitemap, and admin to Django
  if (
    pathname.startsWith("/api/") ||
    pathname.startsWith("/og/") ||
    pathname.startsWith("/admin/") ||
    pathname === "/sitemap.xml"
  ) {
    const target = new URL(pathname + request.nextUrl.search, DJANGO_API_URL);
    const headers = new Headers(request.headers);
    headers.set("Host", new URL(DJANGO_API_URL).host);
    return NextResponse.rewrite(target, {
      request: {
        headers,
      },
    });
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/api/:path*", "/og/:path*", "/admin/:path*", "/sitemap.xml"],
};
