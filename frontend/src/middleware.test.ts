import { describe, it, expect } from "vitest";
import { config } from "./middleware";

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
