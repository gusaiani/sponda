import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

const SYMBOLS = Array.from({ length: 50 }, (_u, i) => `T${i}`);

function stubApi() {
  vi.stubGlobal("fetch", vi.fn(async (input: unknown) => {
    const url = String(input);
    if (url.includes("/api/tickers/symbols/")) {
      return new Response(JSON.stringify({ count: SYMBOLS.length, symbols: SYMBOLS }), { status: 200 });
    }
    if (url.includes("/api/health/")) {
      return new Response(JSON.stringify({ tickers: { last_updated: "2026-08-26T00:00:00Z" } }), { status: 200 });
    }
    return new Response("{}", { status: 404 });
  }));
}

async function get(file: string) {
  const { GET } = await import("./route");
  return GET(new Request(`https://sponda.capital/sitemaps/${file}`), {
    params: Promise.resolve({ file }),
  });
}

describe("GET /sitemaps/[file]", () => {
  beforeEach(stubApi);
  afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

  it("serves the static pages sitemap", async () => {
    const response = await get("pages.xml");
    expect(response.status).toBe(200);
    const xml = await response.text();
    expect(xml).toContain("<urlset");
    expect(xml).toContain("https://sponda.capital/en/screener");
  });

  it("serves a company chunk", async () => {
    const xml = await (await get("companies-0.xml")).text();
    expect(xml).toContain("https://sponda.capital/en/T0");
    expect(xml).toContain("https://sponda.capital/pt/T0/graficos");
  });

  it("is served as XML", async () => {
    expect((await get("companies-0.xml")).headers.get("content-type")).toContain("xml");
  });

  it("404s a chunk beyond the end of the universe", async () => {
    expect((await get("companies-99.xml")).status).toBe(404);
  });

  it("404s a filename that is not one of ours", async () => {
    for (const name of ["companies.xml", "../../etc/passwd", "companies-x.xml", "random.xml"]) {
      expect((await get(name)).status, name).toBe(404);
    }
  });

  it("is cacheable", async () => {
    expect((await get("companies-0.xml")).headers.get("cache-control")).toContain("public");
  });
});
