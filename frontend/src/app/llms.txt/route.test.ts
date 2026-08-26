import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

const CATALOGUE = {
  indicators: [
    { key: "pe10", name: "P/E10", definition: "Market cap over ten-year earnings.", direction: "lower_is_better" },
    { key: "pfcf10", name: "P/FCF10", definition: "Market cap over ten-year free cash flow.", direction: "lower_is_better" },
  ],
  countries: ["BR", "US"],
  sectors: ["Oil", "Mining"],
  unsupported_examples: ["dividend yield", "ROE"],
};

async function body(): Promise<string> {
  const { GET } = await import("./route");
  return (await GET()).text();
}

describe("GET /llms.txt", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(async () =>
      new Response(JSON.stringify(CATALOGUE), { status: 200 })));
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("is served as plain text", async () => {
    const { GET } = await import("./route");
    const response = await GET();
    expect(response.headers.get("content-type")).toContain("text/plain");
  });

  it("documents the .md convention, which is the point of the file", async () => {
    const output = await body();
    expect(output).toContain(".md");
    expect(output).toContain("/{locale}/{TICKER}.md");
  });

  it("uses locale-prefixed URLs, because bare ones 302 away", async () => {
    const output = await body();
    // The old hand-written file advertised /{TICKER}/fundamentos, which the
    // middleware redirects. Every documented URL must carry its locale.
    expect(output).not.toMatch(/https:\/\/sponda\.capital\/\{TICKER\}/);
    expect(output).toContain("https://sponda.capital/{locale}/{TICKER}");
  });

  it("lists the supported locales", async () => {
    const output = await body();
    for (const locale of ["pt", "en", "es", "fr", "de", "it"]) {
      expect(output, locale).toContain(locale);
    }
  });

  it("names the indicators from the live catalogue, not a hand-copied list", async () => {
    const output = await body();
    expect(output).toContain("pe10");
    expect(output).toContain("Market cap over ten-year free cash flow.");
  });

  it("names what Sponda does not track", async () => {
    expect(await body()).toContain("dividend yield");
  });

  it("points at the MCP server and the sitemap", async () => {
    const output = await body();
    expect(output).toContain("/api/mcp");
    expect(output).toContain("/sitemap.xml");
  });

  it("still renders when the catalogue endpoint is down", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("", { status: 500 })));
    const output = await body();
    expect(output).toContain("# Sponda");
    expect(output).toContain("/{locale}/{TICKER}.md");
  });

  it("is cacheable", async () => {
    const { GET } = await import("./route");
    expect((await GET()).headers.get("cache-control")).toContain("public");
  });
});

describe("llms.txt brevity", () => {
  it("collapses the strict P/E window family into one entry", async () => {
    const manyWindows = {
      ...CATALOGUE,
      indicators: [
        ...Array.from({ length: 15 }, (_unused, index) => ({
          key: `pe${index + 1}`,
          name: `P/E${index + 1}`,
          definition: "Market cap over inflation-adjusted earnings.",
          direction: "lower_is_better",
        })),
        { key: "peg", name: "PEG", definition: "P/E10 over growth.", direction: "lower_is_better" },
      ],
    };
    vi.stubGlobal("fetch", vi.fn(async () =>
      new Response(JSON.stringify(manyWindows), { status: 200 })));

    const output = await body();
    expect(output).toContain("`pe1` .. `pe15`");
    expect(output).not.toContain("`pe7` (P/E7)");
    expect(output).toContain("`peg` (PEG)");
  });

  it("uses no em dashes", async () => {
    expect(await body()).not.toContain("\u2014");
  });
});
