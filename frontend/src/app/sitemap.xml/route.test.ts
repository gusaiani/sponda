import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

function stubApi(symbolCount: number) {
  const symbols = Array.from({ length: symbolCount }, (_u, i) => `T${i}`);
  vi.stubGlobal("fetch", vi.fn(async (input: unknown) => {
    const url = String(input);
    if (url.includes("/api/tickers/symbols/")) {
      return new Response(JSON.stringify({ count: symbols.length, symbols }), { status: 200 });
    }
    if (url.includes("/api/health/")) {
      return new Response(JSON.stringify({ tickers: { last_updated: "2026-08-26T00:00:00Z" } }), { status: 200 });
    }
    return new Response("{}", { status: 404 });
  }));
}

async function body() {
  const { GET } = await import("./route");
  return (await GET()).text();
}

describe("GET /sitemap.xml", () => {
  beforeEach(() => stubApi(100));
  afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

  it("is a sitemap index, not a giant urlset", () => {
    // The old Django SitemapView built 600k <url> entries in one document,
    // past the 50,000-URL protocol limit.
    return body().then((xml) => {
      expect(xml).toContain("<sitemapindex");
      expect(xml).not.toContain("<urlset");
    });
  });

  it("is served as XML", async () => {
    const { GET } = await import("./route");
    expect((await GET()).headers.get("content-type")).toContain("xml");
  });

  it("lists the static pages sitemap and at least one company sitemap", async () => {
    const xml = await body();
    expect(xml).toContain("https://sponda.capital/sitemaps/pages.xml");
    expect(xml).toContain("https://sponda.capital/sitemaps/companies-0.xml");
  });

  it("adds a child sitemap for every chunk of the universe", async () => {
    // 18,400 companies x 4 pages x 2 locales = 147,200 entries, well past
    // what one file may hold.
    stubApi(18_400);
    const xml = await body();
    const children = (xml.match(/companies-\d+\.xml/g) ?? []).length;
    expect(children).toBeGreaterThan(1);
  });

  it("still emits the static sitemap when the symbol list is unavailable", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("", { status: 500 })));
    const xml = await body();
    expect(xml).toContain("<sitemapindex");
    expect(xml).toContain("pages.xml");
  });

  it("is cacheable", async () => {
    const { GET } = await import("./route");
    expect((await GET()).headers.get("cache-control")).toContain("public");
  });
});
