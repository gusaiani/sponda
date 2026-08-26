import { describe, it, expect } from "vitest";
import {
  MARKDOWN_EXTENSION,
  MARKDOWN_ROUTE_PREFIX,
  markdownRewritePath,
  markdownUrlFor,
} from "./markdown-routes";

describe("markdownUrlFor", () => {
  it("appends .md to the company page URL", () => {
    expect(markdownUrlFor("en", "PETR4")).toBe("/en/PETR4.md");
  });

  it("uppercases the ticker so one company maps to one URL", () => {
    expect(markdownUrlFor("en", "petr4")).toBe("/en/PETR4.md");
  });

  it("uses the locale's own tab slug", () => {
    expect(markdownUrlFor("pt", "PETR4", "charts")).toBe("/pt/PETR4/graficos.md");
    expect(markdownUrlFor("de", "PETR4", "fundamentals")).toBe("/de/PETR4/fundamentaldaten.md");
  });

  it("drops the slug for the metrics tab, which has none", () => {
    expect(markdownUrlFor("pt", "PETR4", "metrics")).toBe("/pt/PETR4.md");
  });
});

describe("markdownRewritePath", () => {
  it("maps a company page onto the /md handler", () => {
    expect(markdownRewritePath("/en/PETR4.md")).toBe("/md/en/PETR4");
  });

  it("maps a tab page, slug intact", () => {
    expect(markdownRewritePath("/pt/PETR4/graficos.md")).toBe("/md/pt/PETR4/graficos");
  });

  it("maps the screener", () => {
    expect(markdownRewritePath("/en/screener.md")).toBe("/md/en/screener");
  });

  it("maps the home page", () => {
    expect(markdownRewritePath("/pt.md")).toBe("/md/pt");
  });

  it("serves a locale-free ticker in the default locale rather than redirecting", () => {
    // A crawler that guessed the URL should not pay for a hop.
    expect(markdownRewritePath("/PETR4.md")).toBe("/md/en/PETR4");
  });

  it("reads an uppercase two-letter segment as a ticker, not a locale", () => {
    // DE is Deere & Company. Locales are lowercase everywhere in this app,
    // tickers are uppercase, and that is the whole disambiguation rule.
    expect(markdownRewritePath("/DE.md")).toBe("/md/en/DE");
    expect(markdownRewritePath("/de.md")).toBe("/md/de");
  });

  it("uppercases a lowercase ticker in place instead of redirecting", () => {
    expect(markdownRewritePath("/en/petr4.md")).toBe("/md/en/PETR4");
  });

  it("returns null for a path with no .md extension", () => {
    expect(markdownRewritePath("/en/PETR4")).toBeNull();
    expect(markdownRewritePath("/robots.txt")).toBeNull();
    expect(markdownRewritePath("/sitemap.xml")).toBeNull();
    expect(markdownRewritePath("/llms.txt")).toBeNull();
  });

  it("returns null for infrastructure prefixes that happen to end in .md", () => {
    for (const path of [
      "/api/thing.md",
      "/_next/static/chunk.md",
      "/og/en/AAPL.md",
      "/admin/x.md",
      "/static/x.md",
      "/unsubscribe/token.md",
      "/md/en/PETR4.md",
    ]) {
      expect(markdownRewritePath(path), path).toBeNull();
    }
  });

  it("returns null for a path deeper than locale/ticker/tab", () => {
    expect(markdownRewritePath("/en/PETR4/charts/extra.md")).toBeNull();
  });

  it("returns null for a bare .md at the root", () => {
    expect(markdownRewritePath("/.md")).toBeNull();
    expect(markdownRewritePath(MARKDOWN_EXTENSION)).toBeNull();
  });

  it("returns null for an unsupported locale prefix with a tab", () => {
    // /xx/PETR4/charts.md: xx is not a locale, so this would have to be a
    // ticker with two path segments under it, which is not a page.
    expect(markdownRewritePath("/xx/PETR4/charts.md")).toBeNull();
  });

  it("keeps the route prefix and the extension in sync with the exports", () => {
    expect(MARKDOWN_EXTENSION).toBe(".md");
    expect(MARKDOWN_ROUTE_PREFIX).toBe("/md");
    expect(markdownRewritePath("/en/X.md")?.startsWith(MARKDOWN_ROUTE_PREFIX)).toBe(true);
  });
});

describe("named routes under a locale", () => {
  it("leaves the screener name alone instead of reading it as a ticker", () => {
    expect(markdownRewritePath("/pt/screener.md")).toBe("/md/pt/screener");
  });

  it("returns null for auth, account and social pages", () => {
    for (const route of ["login", "account", "alertas", "user", "spond", "shared"]) {
      expect(markdownRewritePath(`/en/${route}.md`), route).toBeNull();
    }
  });

  it("returns null for a locale-free named route", () => {
    expect(markdownRewritePath("/login.md")).toBeNull();
  });

  it("returns null for a tab under a named route", () => {
    expect(markdownRewritePath("/en/screener/extra.md")).toBeNull();
  });
});
