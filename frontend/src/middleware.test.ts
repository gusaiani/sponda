import { describe, it, expect } from "vitest";
import { NextRequest } from "next/server";
import { config, middleware, LANGUAGE_COOKIE_NAME } from "./middleware";

function buildRequest(
  pathname: string,
  options: { acceptLanguage?: string; cookies?: Record<string, string> } = {},
): NextRequest {
  const url = new URL(`https://sponda.capital${pathname}`);
  const headers = new Headers();
  if (options.acceptLanguage) headers.set("Accept-Language", options.acceptLanguage);
  if (options.cookies) {
    headers.set(
      "Cookie",
      Object.entries(options.cookies).map(([k, v]) => `${k}=${v}`).join("; "),
    );
  }
  return new NextRequest(url, { headers });
}

function cookieValue(response: Response, name: string): string | undefined {
  const header = response.headers.get("set-cookie");
  if (!header) return undefined;
  const match = header.split(/,\s*/).find((c) => c.startsWith(`${name}=`));
  return match?.split(";")[0].split("=")[1];
}

function resolveMatcher(raw: unknown): string[] {
  if (Array.isArray(raw)) return raw as string[];
  if (typeof raw === "string") return [raw];
  return [];
}

/**
 * Turn a Next.js matcher string into a RegExp the same way Next.js does:
 *   - leading "/" is preserved
 *   - ":path*" becomes a non-greedy wildcard (ignored here; covered by .* in the real pattern)
 *   - bare regex-like matchers are used as-is
 * We only implement enough to cover the matchers in our middleware.
 */
function matcherToRegex(matcher: string): RegExp {
  if (matcher.includes(":path*")) {
    const prefix = matcher.replace("/:path*", "");
    return new RegExp(`^${prefix}(/.*)?$`);
  }
  return new RegExp(`^${matcher}$`);
}

function pathIsMatched(pathname: string): boolean {
  const matchers = resolveMatcher(config.matcher);
  return matchers.some((matcher) => matcherToRegex(matcher).test(pathname));
}

describe("middleware config.matcher", () => {
  it("matches /api/* paths so they get proxied to Django", () => {
    expect(pathIsMatched("/api/auth/me/")).toBe(true);
    expect(pathIsMatched("/api/quote/PETR4/")).toBe(true);
  });

  it("matches /api/logos/*.png so logo images get proxied (the dot must not disqualify them)", () => {
    expect(pathIsMatched("/api/logos/PETR4.png")).toBe(true);
    expect(pathIsMatched("/api/logos/BRK.B.png")).toBe(true);
  });

  it("matches /og/* and /admin/* paths", () => {
    expect(pathIsMatched("/og/PETR4")).toBe(true);
    expect(pathIsMatched("/admin/login/")).toBe(true);
  });

  it("matches locale-prefixed app pages", () => {
    expect(pathIsMatched("/pt/PETR4")).toBe(true);
    expect(pathIsMatched("/en")).toBe(true);
  });

  it("does not match Next.js internal asset paths (_next, favicon, fonts, images)", () => {
    expect(pathIsMatched("/_next/static/chunks/main.js")).toBe(false);
    expect(pathIsMatched("/favicon.svg")).toBe(false);
    expect(pathIsMatched("/fonts/Satoshi-Medium.woff2")).toBe(false);
    expect(pathIsMatched("/images/hero.png")).toBe(false);
  });
});

describe("middleware locale persistence", () => {
  it("writes sponda-lang cookie when path is already locale-prefixed", async () => {
    const response = await middleware(buildRequest("/it/PETR4"));
    expect(cookieValue(response, LANGUAGE_COOKIE_NAME)).toBe("it");
  });

  it("writes sponda-lang cookie when redirecting bare URL to chosen locale", async () => {
    const response = await middleware(
      buildRequest("/", { acceptLanguage: "fr-CA,fr;q=0.9,en;q=0.8" }),
    );
    expect(response.status).toBe(302);
    expect(cookieValue(response, LANGUAGE_COOKIE_NAME)).toBe("fr");
    expect(response.headers.get("location")).toContain("/fr");
  });

  it("prefers existing cookie over Accept-Language on bare URL", async () => {
    const response = await middleware(
      buildRequest("/", {
        acceptLanguage: "en",
        cookies: { [LANGUAGE_COOKIE_NAME]: "de" },
      }),
    );
    expect(cookieValue(response, LANGUAGE_COOKIE_NAME)).toBe("de");
    expect(response.headers.get("location")).toContain("/de");
  });

  it("bare URL with session cookie but no sponda-lang falls through to Accept-Language", async () => {
    const response = await middleware(
      buildRequest("/", {
        cookies: { sessionid: "abc" },
        acceptLanguage: "fr-FR,fr;q=0.9,en;q=0.8",
      }),
    );
    expect(response.headers.get("location")).toContain("/fr");
    expect(cookieValue(response, LANGUAGE_COOKIE_NAME)).toBe("fr");
  });
});

describe("middleware ticker case normalization", () => {
  it("301 redirects lowercase ticker to uppercase when locale-prefixed", async () => {
    const response = await middleware(buildRequest("/en/petr4"));
    expect(response.status).toBe(301);
    expect(response.headers.get("location")).toContain("/en/PETR4");
  });

  it("301 redirects mixed-case ticker to uppercase", async () => {
    const response = await middleware(buildRequest("/pt/PeTr4"));
    expect(response.status).toBe(301);
    expect(response.headers.get("location")).toContain("/pt/PETR4");
  });

  it("301 redirects lowercase ticker with tab slug", async () => {
    const response = await middleware(buildRequest("/en/petr4/charts"));
    expect(response.status).toBe(301);
    expect(response.headers.get("location")).toContain("/en/PETR4/charts");
  });

  it("does not redirect already uppercase ticker", async () => {
    const response = await middleware(buildRequest("/en/PETR4"));
    expect(response.status).toBe(200);
  });

  it("does not uppercase known locale routes like screener", async () => {
    const response = await middleware(buildRequest("/en/screener"));
    expect(response.status).toBe(200);
  });

  it("does not uppercase known locale routes like shared", async () => {
    const response = await middleware(buildRequest("/en/shared/abc123"));
    expect(response.status).toBe(200);
  });

  it("normalizes ticker case in bare URL redirect", async () => {
    const response = await middleware(
      buildRequest("/petr4", { cookies: { [LANGUAGE_COOKIE_NAME]: "en" } }),
    );
    expect(response.status).toBe(302);
    expect(response.headers.get("location")).toContain("/en/PETR4");
  });

  it("does not uppercase bare known routes", async () => {
    const response = await middleware(
      buildRequest("/screener", { cookies: { [LANGUAGE_COOKIE_NAME]: "en" } }),
    );
    expect(response.status).toBe(302);
    expect(response.headers.get("location")).toContain("/en/screener");
    expect(response.headers.get("location")).not.toContain("/en/SCREENER");
  });
});
