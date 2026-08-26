import { describe, it, expect } from "vitest";
import {
  MAX_URLS_PER_SITEMAP,
  chunk,
  companySitemapName,
  parseSitemapName,
  renderSitemapIndex,
  renderUrlSet,
  buildCompanyEntries,
  buildStaticEntries,
} from "./sitemap";

describe("chunk", () => {
  it("splits into pieces of at most the given size", () => {
    expect(chunk([1, 2, 3, 4, 5], 2)).toEqual([[1, 2], [3, 4], [5]]);
  });

  it("returns nothing for an empty list", () => {
    expect(chunk([], 10)).toEqual([]);
  });

  it("keeps a list shorter than the chunk size in one piece", () => {
    expect(chunk([1, 2], 10)).toEqual([[1, 2]]);
  });
});

describe("sitemap file names", () => {
  it("round-trips an index", () => {
    expect(parseSitemapName(companySitemapName(3))).toBe(3);
  });

  it("names files predictably so crawlers see stable URLs", () => {
    expect(companySitemapName(0)).toBe("companies-0.xml");
  });

  it("rejects anything that is not one of ours", () => {
    for (const name of ["companies.xml", "companies-x.xml", "../etc.xml", "companies-1", ""]) {
      expect(parseSitemapName(name), name).toBeNull();
    }
  });

  it("rejects a negative or fractional index", () => {
    expect(parseSitemapName("companies--1.xml")).toBeNull();
    expect(parseSitemapName("companies-1.5.xml")).toBeNull();
  });
});

describe("buildCompanyEntries", () => {
  const entries = buildCompanyEntries(["PETR4", "VALE3"], "2026-08-26T00:00:00Z");

  it("emits the company page and its tabs, per sitemap locale", () => {
    const urls = entries.map((e) => e.url);
    expect(urls).toContain("https://sponda.capital/en/PETR4");
    expect(urls).toContain("https://sponda.capital/en/PETR4/charts");
    expect(urls).toContain("https://sponda.capital/pt/PETR4/graficos");
    expect(urls).toContain("https://sponda.capital/pt/VALE3/fundamentos");
  });

  it("uses each locale's own tab slug", () => {
    const urls = entries.map((e) => e.url);
    expect(urls).not.toContain("https://sponda.capital/pt/PETR4/charts");
  });

  it("produces one entry per company per tab per sitemap locale", () => {
    // 2 companies x 4 pages x 2 locales
    expect(entries).toHaveLength(16);
  });

  it("advertises every indexable locale as an alternate", () => {
    const alternates = entries[0].alternates?.languages ?? {};
    expect(alternates["pt-BR"]).toBeDefined();
    expect(alternates["en"]).toBeDefined();
    expect(alternates["x-default"]).toBe(alternates["en"]);
  });

  it("never advertises a noindex locale as an alternate", () => {
    const alternates = entries[0].alternates?.languages ?? {};
    expect(alternates["zh"]).toBeUndefined();
  });

  it("is empty for no companies", () => {
    expect(buildCompanyEntries([], "2026-08-26T00:00:00Z")).toEqual([]);
  });
});

describe("buildStaticEntries", () => {
  it("includes the home page and the screener", () => {
    const urls = buildStaticEntries("2026-08-26T00:00:00Z").map((e) => e.url);
    expect(urls).toContain("https://sponda.capital/en");
    expect(urls).toContain("https://sponda.capital/pt/screener");
  });

  it("does not list auth or social pages, which robots.txt disallows", () => {
    // Compare on the path only. The hostname itself contains "/spond".
    const paths = buildStaticEntries("2026-08-26T00:00:00Z")
      .map((e) => new URL(e.url).pathname);
    for (const disallowed of ["/login", "/account", "/user", "/spond", "/alertas", "/visitas"]) {
      expect(paths.some((p) => p.includes(disallowed)), disallowed).toBe(false);
    }
  });
});

describe("renderUrlSet", () => {
  const xml = renderUrlSet([
    {
      url: "https://sponda.capital/en/PETR4",
      lastModified: "2026-08-26T00:00:00Z",
      changeFrequency: "daily",
      priority: 0.8,
      alternates: { languages: { "pt-BR": "https://sponda.capital/pt/PETR4", en: "https://sponda.capital/en/PETR4" } },
    },
  ]);

  it("is a well-formed urlset with the xhtml namespace", () => {
    expect(xml).toContain('<?xml version="1.0" encoding="UTF-8"?>');
    expect(xml).toContain('xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"');
    expect(xml).toContain('xmlns:xhtml="http://www.w3.org/1999/xhtml"');
  });

  it("emits loc, lastmod, changefreq and priority", () => {
    expect(xml).toContain("<loc>https://sponda.capital/en/PETR4</loc>");
    expect(xml).toContain("<lastmod>2026-08-26T00:00:00Z</lastmod>");
    expect(xml).toContain("<changefreq>daily</changefreq>");
    expect(xml).toContain("<priority>0.8</priority>");
  });

  it("emits hreflang alternates", () => {
    expect(xml).toContain('<xhtml:link rel="alternate" hreflang="pt-BR" href="https://sponda.capital/pt/PETR4"/>');
  });

  it("escapes ampersands so one odd symbol cannot break the document", () => {
    const escaped = renderUrlSet([{ url: "https://sponda.capital/en/A&B" }]);
    expect(escaped).toContain("<loc>https://sponda.capital/en/A&amp;B</loc>");
    expect(escaped).not.toContain("/A&B<");
  });
});

describe("renderSitemapIndex", () => {
  const xml = renderSitemapIndex(
    ["https://sponda.capital/sitemaps/pages.xml", "https://sponda.capital/sitemaps/companies-0.xml"],
    "2026-08-26T00:00:00Z",
  );

  it("is a sitemapindex, not a urlset", () => {
    expect(xml).toContain("<sitemapindex");
    expect(xml).not.toContain("<urlset");
  });

  it("lists each child with a lastmod", () => {
    expect(xml).toContain("<loc>https://sponda.capital/sitemaps/companies-0.xml</loc>");
    expect(xml).toContain("<lastmod>2026-08-26T00:00:00Z</lastmod>");
  });
});

describe("size limits", () => {
  it("stays under the 50,000 URL ceiling per file", () => {
    expect(MAX_URLS_PER_SITEMAP).toBeLessThanOrEqual(50_000);
  });

  it("leaves headroom for hreflang alternates against the 50MB limit", () => {
    // Each entry carries up to six xhtml:link lines, so the bytes per URL are
    // several times a bare <loc>. 50k entries at that size would approach the
    // uncompressed size limit.
    expect(MAX_URLS_PER_SITEMAP).toBeLessThanOrEqual(20_000);
  });
});

describe("SYMBOLS_PER_SITEMAP", () => {
  it("keeps a full chunk inside the per-file URL ceiling", async () => {
    const { SYMBOLS_PER_SITEMAP } = await import("./sitemap");
    const symbols = Array.from({ length: SYMBOLS_PER_SITEMAP }, (_u, i) => `T${i}`);
    const entries = buildCompanyEntries(symbols, "2026-08-26T00:00:00Z");
    expect(entries.length).toBeLessThanOrEqual(MAX_URLS_PER_SITEMAP);
  });

  it("does not leave most of a file empty", async () => {
    const { SYMBOLS_PER_SITEMAP } = await import("./sitemap");
    const symbols = Array.from({ length: SYMBOLS_PER_SITEMAP }, (_u, i) => `T${i}`);
    const entries = buildCompanyEntries(symbols, "2026-08-26T00:00:00Z");
    expect(entries.length).toBeGreaterThan(MAX_URLS_PER_SITEMAP * 0.9);
  });
});
