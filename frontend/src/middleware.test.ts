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

  it("does NOT match the assistant SSE route, so the buffering rewrite never touches it", () => {
    // /api/assistant/ask returns text/event-stream. Routing it through the
    // middleware's NextResponse.rewrite() buffers the whole body (same bug
    // that forced the /api/logos/ nginx bypass), killing token-by-token
    // delivery. nginx proxies this path straight to Django; middleware skips it.
    expect(pathIsMatched("/api/assistant/ask")).toBe(false);

    // Every other /api/ path must still be proxied exactly as before.
    expect(pathIsMatched("/api/auth/me/")).toBe(true);
    expect(pathIsMatched("/api/logos/PETR4.png")).toBe(true);
  });

  it("matches /og/* and /admin/* paths", () => {
    expect(pathIsMatched("/og/PETR4")).toBe(true);
    expect(pathIsMatched("/admin/login/")).toBe(true);
  });

  it("matches /og/*.png so the card route is reached despite the dot", () => {
    expect(pathIsMatched("/og/pt/PETR4.png")).toBe(true);
    expect(pathIsMatched("/og/en/BRK-B.png")).toBe(true);
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

describe("middleware Django static file proxying", () => {
  // Django admin's stylesheets live under /static/. The catch-all matcher
  // skips any path with a dot, so without an explicit matcher the request
  // dies inside Next as a 404 and the admin renders unstyled.
  it("matches /static/* despite the dot in the filename", () => {
    expect(pathIsMatched("/static/admin/css/base.css")).toBe(true);
    expect(pathIsMatched("/static/admin/img/search.svg")).toBe(true);
  });

  it("rewrites static files to Django, which serves them", async () => {
    const response = await middleware(
      buildRequest("/static/admin/css/base.css"),
    );

    expect(response.headers.get("x-middleware-rewrite")).toContain(
      "/static/admin/css/base.css",
    );
  });

  it("never prefixes a static URL with a locale", async () => {
    const response = await middleware(
      buildRequest("/static/admin/css/base.css"),
    );

    expect(response.headers.get("location")).toBeNull();
  });
});

describe("middleware unsubscribe proxying", () => {
  // A real django.core.signing token: compressed payloads start with a dot,
  // and the three parts are separated by colons. Both characters have to
  // survive the trip, which is why this is a literal rather than "abc".
  const SIGNED_TOKEN =
    ".eJyrViouLU7OSC1WsjLUUcpLLVeyMjQwMNWpBQBLhAcC:1uMv8k:qMoCd1jDPfPZLZ0PYhHXKa5Y2Nc";

  it("matches /unsubscribe/* even when the signed token contains a dot", () => {
    expect(pathIsMatched(`/unsubscribe/${SIGNED_TOKEN}/`)).toBe(true);
  });

  it("rewrites the unsubscribe page to Django, which renders it", async () => {
    const response = await middleware(buildRequest(`/unsubscribe/${SIGNED_TOKEN}/`));

    expect(response.headers.get("x-middleware-rewrite")).toContain(
      `/unsubscribe/${SIGNED_TOKEN}/`,
    );
  });

  it("never prefixes the unsubscribe URL with a locale", async () => {
    // The link lives in an inbox forever. A locale redirect would break the
    // signature-carrying path and strand the reader on a 404.
    const response = await middleware(buildRequest(`/unsubscribe/${SIGNED_TOKEN}/`));

    expect(response.headers.get("location")).toBeNull();
  });
});

describe("middleware Open Graph card routing", () => {
  // /og/ used to be proxied to Django, which has no routes there: its
  // catch-all answered with the legacy SPA shell, i.e. HTML with a 200 to a
  // crawler asking for an image. The cards are a Next route now, so the
  // middleware has to let them through untouched.
  it("does not rewrite the card path to Django", async () => {
    const response = await middleware(buildRequest("/og/pt/PETR4.png"));

    expect(response.headers.get("x-middleware-rewrite")).toBeNull();
  });

  it("never prefixes a card URL with a locale", async () => {
    // The locale is already a path segment, and a redirect would cost every
    // crawler an extra round trip on an image it is impatient about.
    const response = await middleware(buildRequest("/og/pt/PETR4.png"));

    expect(response.headers.get("location")).toBeNull();
    expect(response.status).toBe(200);
  });

  it("still proxies /api/ and /admin/ to Django", async () => {
    const apiResponse = await middleware(buildRequest("/api/quote/PETR4/"));
    const adminResponse = await middleware(buildRequest("/admin/login/"));

    expect(apiResponse.headers.get("x-middleware-rewrite")).toContain("/api/quote/PETR4/");
    expect(adminResponse.headers.get("x-middleware-rewrite")).toContain("/admin/login/");
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
  it("redirects lowercase ticker to uppercase when locale-prefixed", async () => {
    const response = await middleware(buildRequest("/en/petr4"));
    expect(response.status).toBe(302);
    expect(response.headers.get("location")).toContain("/en/PETR4");
  });

  it("redirects mixed-case ticker to uppercase", async () => {
    const response = await middleware(buildRequest("/pt/PeTr4"));
    expect(response.status).toBe(302);
    expect(response.headers.get("location")).toContain("/pt/PETR4");
  });

  it("redirects lowercase ticker with tab slug", async () => {
    const response = await middleware(buildRequest("/en/petr4/charts"));
    expect(response.status).toBe(302);
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

describe("middleware markdown routing", () => {
  // The catch-all matcher excludes any path containing a dot, so .md URLs
  // reach the middleware only because of an explicit matcher entry. Without
  // it they fall straight through to the filesystem and 404.
  it("matches .md paths", () => {
    expect(pathIsMatched("/en/PETR4.md")).toBe(true);
    expect(pathIsMatched("/pt/PETR4/graficos.md")).toBe(true);
    expect(pathIsMatched("/PETR4.md")).toBe(true);
    expect(pathIsMatched("/en.md")).toBe(true);
  });

  it("rewrites a company page onto the markdown handler", async () => {
    const response = await middleware(buildRequest("/en/PETR4.md"));
    expect(response.headers.get("x-middleware-rewrite")).toContain("/md/en/PETR4");
  });

  it("rewrites a tab page, slug intact", async () => {
    const response = await middleware(buildRequest("/pt/PETR4/graficos.md"));
    expect(response.headers.get("x-middleware-rewrite")).toContain("/md/pt/PETR4/graficos");
  });

  it("rewrites the screener and the home page", async () => {
    const screener = await middleware(buildRequest("/en/screener.md"));
    expect(screener.headers.get("x-middleware-rewrite")).toContain("/md/en/screener");

    const home = await middleware(buildRequest("/pt.md"));
    expect(home.headers.get("x-middleware-rewrite")).toContain("/md/pt");
  });

  it("serves a locale-free markdown URL without a redirect", async () => {
    // A model that guessed the URL from an HTML link should get the document,
    // not a 302 into a locale it did not ask for.
    const response = await middleware(buildRequest("/PETR4.md"));
    expect(response.status).toBe(200);
    expect(response.headers.get("location")).toBeNull();
    expect(response.headers.get("x-middleware-rewrite")).toContain("/md/en/PETR4");
  });

  it("uppercases the ticker in place instead of redirecting", async () => {
    const response = await middleware(buildRequest("/en/petr4.md"));
    expect(response.headers.get("location")).toBeNull();
    expect(response.headers.get("x-middleware-rewrite")).toContain("/md/en/PETR4");
  });

  it("preserves the query string", async () => {
    const url = new URL("https://sponda.capital/en/PETR4.md?utm_source=x");
    const response = await middleware(new NextRequest(url, { headers: new Headers() }));
    expect(response.headers.get("x-middleware-rewrite")).toContain("utm_source=x");
  });

  it("does not rewrite an Open Graph card that ends in .md", async () => {
    const response = await middleware(buildRequest("/og/en/AAPL.md"));
    expect(response.headers.get("x-middleware-rewrite") ?? "").not.toContain("/md/");
  });

  it("still proxies /api/ paths that end in .md to Django", async () => {
    const response = await middleware(buildRequest("/api/thing.md"));
    const rewrite = response.headers.get("x-middleware-rewrite") ?? "";
    expect(rewrite).toContain("/api/thing.md");
    expect(rewrite).not.toContain("/md/");
  });

  it("leaves robots.txt, sitemap.xml and llms.txt alone", async () => {
    for (const path of ["/robots.txt", "/sitemap.xml", "/llms.txt"]) {
      expect(pathIsMatched(path), path).toBe(false);
    }
  });

  it("does not publish auth or social pages as markdown", async () => {
    for (const path of ["/en/login.md", "/en/account.md", "/en/user.md"]) {
      const response = await middleware(buildRequest(path));
      expect(response.headers.get("x-middleware-rewrite") ?? "", path).not.toContain("/md/");
    }
  });

  it("404s a .md URL we do not publish", async () => {
    // Falling through would send /en/login.md to the ticker-case rule, which
    // redirects to /en/LOGIN.MD, where [locale]/[ticker] answers 200 with an
    // HTML shell. A crawler reading that as a real markdown page is worse
    // than a miss.
    for (const path of ["/en/login.md", "/xx/AAPL.md", "/en/screener/extra.md"]) {
      const response = await middleware(buildRequest(path));
      expect(response.status, path).toBe(404);
      expect(response.headers.get("location"), path).toBeNull();
      expect(response.headers.get("content-type"), path).toContain("text/markdown");
    }
  });

  it("does not cache a markdown 404", async () => {
    // A ticker we do not know today we may know tomorrow, and Cloudflare
    // would otherwise pin the miss for hours.
    const response = await middleware(buildRequest("/en/login.md"));
    expect(response.headers.get("cache-control")).toContain("no-store");
  });
});

describe("middleware markdown Link header", () => {
  // A crawler that issues HEAD never parses the body, so it cannot see the
  // <link rel="alternate"> tag. The header is how it learns the markdown
  // twin exists. HEAD against /api/ was 500ing until nginx started routing
  // it directly, so these probes are only now worth serving well.
  it("advertises the markdown twin of a company page", async () => {
    const response = await middleware(buildRequest("/en/PETR4"));
    expect(response.headers.get("link")).toBe(
      '<https://sponda.capital/en/PETR4.md>; rel="alternate"; type="text/markdown"',
    );
  });

  it("advertises the twin of a tab, with the locale's own slug", async () => {
    const response = await middleware(buildRequest("/pt/PETR4/graficos"));
    expect(response.headers.get("link")).toContain("/pt/PETR4/graficos.md");
  });

  it("advertises the screener and the home page", async () => {
    expect((await middleware(buildRequest("/en/screener"))).headers.get("link"))
      .toContain("/en/screener.md");
    expect((await middleware(buildRequest("/pt"))).headers.get("link"))
      .toContain("/pt.md");
  });

  it("sends no Link header for pages with no markdown twin", async () => {
    for (const path of ["/en/login", "/en/account", "/en/user/gustavo"]) {
      expect((await middleware(buildRequest(path))).headers.get("link"), path).toBeNull();
    }
  });

  it("sends no Link header on the markdown page itself", async () => {
    expect((await middleware(buildRequest("/en/PETR4.md"))).headers.get("link")).toBeNull();
  });

  it("sends no Link header on a redirect", async () => {
    // A bare path is about to be redirected to a locale-prefixed one.
    const response = await middleware(buildRequest("/PETR4"));
    expect(response.status).toBe(302);
    expect(response.headers.get("link")).toBeNull();
  });
});
