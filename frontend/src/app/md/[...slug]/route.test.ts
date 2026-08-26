import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

const SNAPSHOT = {
  symbol: "PETR4",
  name: "Petrobras",
  sector: "Oil",
  country: "BR",
  reported_currency: "BRL",
  market_cap: 400_000_000_000,
  current_price: 35.75,
  computed_at: "2026-08-26T12:00:00+00:00",
  pe10: 6.5,
  pe_years_available: 15,
  pfcf10: 8,
};

const CATALOGUE = {
  indicators: [
    { key: "pe10", name: "P/E10", definition: "Market cap over ten-year earnings.", direction: "lower_is_better", note: "Cheap below 10." },
  ],
  countries: ["BR", "US"],
  sectors: ["Oil"],
  unsupported_examples: ["dividend yield"],
};

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

/** Route the fake API by URL, the way the real Django server would. */
function stubApi(overrides: Record<string, () => Response> = {}) {
  vi.stubGlobal("fetch", vi.fn(async (input: unknown) => {
    const url = String(input);
    for (const [fragment, respond] of Object.entries(overrides)) {
      if (url.includes(fragment)) return respond();
    }
    if (url.includes("/assistant/indicators/")) return jsonResponse(CATALOGUE);
    if (url.includes("/indicators/")) return jsonResponse(SNAPSHOT);
    if (url.includes("/analysis/")) return jsonResponse({}, 404);
    if (url.includes("/peers/")) return jsonResponse([]);
    return jsonResponse({}, 404);
  }));
}

async function get(slug: string[]) {
  const { GET } = await import("./route");
  return GET(new Request("https://sponda.capital/md/" + slug.join("/")), {
    params: Promise.resolve({ slug }),
  });
}

describe("GET /md/[...slug]", () => {
  beforeEach(() => stubApi());
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("serves a company page as markdown", async () => {
    const response = await get(["en", "PETR4"]);
    expect(response.status).toBe(200);
    expect(await response.text()).toContain("# Petrobras (PETR4)");
  });

  it("declares itself as markdown, not HTML", async () => {
    const response = await get(["en", "PETR4"]);
    expect(response.headers.get("content-type")).toBe("text/markdown; charset=utf-8");
  });

  it("is cacheable at the browser, the edge, and while revalidating", async () => {
    const cacheControl = (await get(["en", "PETR4"])).headers.get("cache-control") ?? "";
    expect(cacheControl).toContain("public");
    expect(cacheControl).toContain("max-age=");
    expect(cacheControl).toContain("s-maxage=");
    expect(cacheControl).toContain("stale-while-revalidate=");
  });

  it("accepts a lowercase ticker without redirecting", async () => {
    const response = await get(["en", "petr4"]);
    expect(response.status).toBe(200);
    expect(await response.text()).toContain("(PETR4)");
  });

  it("serves every supported locale", async () => {
    for (const locale of ["pt", "en", "es", "zh", "fr", "de", "it"]) {
      expect((await get([locale, "PETR4"])).status, locale).toBe(200);
    }
  });

  it("404s an unsupported locale", async () => {
    expect((await get(["xx", "PETR4"])).status).toBe(404);
  });

  it("404s a ticker the API does not know", async () => {
    stubApi({ "/indicators/": () => jsonResponse({}, 404) });
    expect((await get(["en", "NOPE99"])).status).toBe(404);
  });

  it("does not let a 404 linger in a cache", async () => {
    stubApi({ "/indicators/": () => jsonResponse({}, 404) });
    const response = await get(["en", "NOPE99"]);
    expect(response.headers.get("cache-control")).toContain("no-store");
  });

  it("serves the tab pages", async () => {
    for (const [locale, slug] of [["en", "charts"], ["pt", "graficos"], ["de", "fundamentaldaten"]]) {
      const response = await get([locale, "PETR4", slug]);
      expect(response.status, `${locale}/${slug}`).toBe(200);
    }
  });

  it("404s a tab slug from the wrong locale", async () => {
    // /en/PETR4/graficos.md: graficos is the Portuguese slug.
    expect((await get(["en", "PETR4", "graficos"])).status).toBe(404);
  });

  it("404s an unrecognised tab slug", async () => {
    expect((await get(["en", "PETR4", "nonsense"])).status).toBe(404);
  });

  it("serves the screener glossary", async () => {
    const response = await get(["en", "screener"]);
    expect(response.status).toBe(200);
    const body = await response.text();
    expect(body).toContain("pe10");
    expect(body).toContain("Market cap over ten-year earnings.");
  });

  it("names what Sponda does not track on the screener page", async () => {
    const body = await (await get(["en", "screener"])).text();
    expect(body).toContain("dividend yield");
  });

  it("serves the home page", async () => {
    const response = await get(["en"]);
    expect(response.status).toBe(200);
    expect(await response.text()).toContain("Sponda");
  });

  it("404s an empty slug", async () => {
    expect((await get([])).status).toBe(404);
  });

  it("404s a slug deeper than locale/ticker/tab", async () => {
    expect((await get(["en", "PETR4", "charts", "extra"])).status).toBe(404);
  });

  it("never reaches the quota-gated quote endpoint", async () => {
    await get(["en", "PETR4"]);
    await get(["en", "PETR4", "fundamentals"]);
    await get(["en", "PETR4", "charts"]);
    const fetchMock = globalThis.fetch as unknown as { mock: { calls: unknown[][] } };
    for (const call of fetchMock.mock.calls) {
      const url = String(call[0]);
      expect(url, url).not.toMatch(/\/api\/quote\/[^/]+\/$/);
      expect(url, url).not.toContain("/multiples-history/");
      expect(url, url).not.toContain("/quote/PETR4/fundamentals/");
    }
  });
});

describe("GET /md/[locale]/for-ai", () => {
  beforeEach(() => stubApi());
  afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

  it("serves the AI access page as markdown", async () => {
    const response = await get(["en", "for-ai"]);
    expect(response.status).toBe(200);
    const body = await response.text();
    expect(body).toContain("# Reading Sponda from a program");
    expect(body).toContain("https://sponda.capital/api/mcp");
  });

  it("renders from the same source as the HTML page", async () => {
    const { AI_ACCESS_SECTIONS } = await import("../../../lib/ai-access-copy");
    const body = await (await get(["en", "for-ai"])).text();
    for (const section of AI_ACCESS_SECTIONS) {
      expect(body, section.heading).toContain(`## ${section.heading}`);
    }
  });

  it("serves it in every locale", async () => {
    for (const locale of ["pt", "en", "de"]) {
      expect((await get([locale, "for-ai"])).status, locale).toBe(200);
    }
  });

  it("404s a tab under it", async () => {
    expect((await get(["en", "for-ai", "extra"])).status).toBe(404);
  });
});
