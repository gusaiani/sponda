import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { getOgImageUrl, generateTickerMetadata, generateScreenerMetadata, MAX_TITLE_LENGTH } from "./metadata";

describe("getOgImageUrl", () => {
  it("returns the Portuguese OG image for pt", () => {
    expect(getOgImageUrl("pt")).toBe("/images/sponda-og-v2.jpg");
  });

  it("returns the English OG image for en", () => {
    expect(getOgImageUrl("en")).toBe("/images/sponda-og-en-v2.jpg");
  });

  it("returns the English OG image for all other supported locales", () => {
    expect(getOgImageUrl("es")).toBe("/images/sponda-og-en-v2.jpg");
    expect(getOgImageUrl("zh")).toBe("/images/sponda-og-en-v2.jpg");
    expect(getOgImageUrl("fr")).toBe("/images/sponda-og-en-v2.jpg");
    expect(getOgImageUrl("de")).toBe("/images/sponda-og-en-v2.jpg");
    expect(getOgImageUrl("it")).toBe("/images/sponda-og-en-v2.jpg");
  });
});

describe("generateTickerMetadata Open Graph image", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(async () => ({
      ok: true,
      json: async () => ({ name: "Vulcabras", sector: "Consumer Non-Durables" }),
    })));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("declares og:type so crawlers do not have to infer it", async () => {
    const metadata = await generateTickerMetadata("VULC3", "pt");

    expect((metadata.openGraph as { type?: string } | undefined)?.type).toBe("website");
  });

  it("points Open Graph and Twitter at the company's own card, not the shared JPEG", async () => {
    const metadata = await generateTickerMetadata("VULC3", "pt");
    const expectedUrl = "https://sponda.capital/og/pt/VULC3.png";

    const openGraphImages = metadata.openGraph?.images as Array<{ url: string }>;
    expect(openGraphImages[0].url).toBe(expectedUrl);
    expect(metadata.twitter?.images).toEqual([expectedUrl]);
  });

  it("gives each locale a distinct card URL", async () => {
    const english = await generateTickerMetadata("VULC3", "en");

    const openGraphImages = english.openGraph?.images as Array<{ url: string }>;
    expect(openGraphImages[0].url).toBe("https://sponda.capital/og/en/VULC3.png");
  });

  it("declares the image MIME type and alt text for the card renderer", async () => {
    const metadata = await generateTickerMetadata("VULC3", "pt");

    const openGraphImages = metadata.openGraph?.images as Array<{
      type: string;
      alt: string;
      width: number;
      height: number;
    }>;
    expect(openGraphImages[0].type).toBe("image/png");
    expect(openGraphImages[0].alt).toContain("VULC3");
    expect(openGraphImages[0].width).toBe(1200);
    expect(openGraphImages[0].height).toBe(630);
  });
});

describe("homepage Open Graph image", () => {
  it("still uses the static locale JPEG, which has no company to render", () => {
    expect(getOgImageUrl("pt")).toBe("/images/sponda-og-v2.jpg");
  });
});

describe("markdown alternate", () => {
  it("advertises the markdown twin of a company page", async () => {
    const metadata = await generateTickerMetadata("PETR4", "en");
    expect(metadata.alternates?.types?.["text/markdown"]).toBe(
      "https://sponda.capital/en/PETR4.md",
    );
  });

  it("points at the markdown twin of the tab, not the company root", async () => {
    const metadata = await generateTickerMetadata("PETR4", "pt", "graficos");
    expect(metadata.alternates?.types?.["text/markdown"]).toBe(
      "https://sponda.capital/pt/PETR4/graficos.md",
    );
  });
});

describe("Dataset distribution", () => {
  async function dataset(ticker: string, locale: string, tabSlug?: string) {
    const metadata = await generateTickerMetadata(ticker, locale as never, tabSlug);
    const schemas = JSON.parse(metadata.other?.["structured-data"] as string);
    return schemas.find((s: { "@type": string }) => s["@type"] === "Dataset");
  }

  it("advertises the markdown twin as a distribution", async () => {
    // schema.org's `distribution` is the standard vocabulary for "the
    // machine-readable version of this page lives here".
    const distributions = (await dataset("PETR4", "en")).distribution;
    const markdown = distributions.find(
      (d: { encodingFormat: string }) => d.encodingFormat === "text/markdown",
    );
    expect(markdown.contentUrl).toBe("https://sponda.capital/en/PETR4.md");
  });

  it("advertises the JSON endpoint as a distribution", async () => {
    const distributions = (await dataset("PETR4", "en")).distribution;
    const json = distributions.find(
      (d: { encodingFormat: string }) => d.encodingFormat === "application/json",
    );
    expect(json.contentUrl).toBe("https://sponda.capital/api/tickers/PETR4/indicators/");
  });

  it("points the markdown distribution at the tab being viewed", async () => {
    const distributions = (await dataset("PETR4", "pt", "graficos")).distribution;
    const markdown = distributions.find(
      (d: { encodingFormat: string }) => d.encodingFormat === "text/markdown",
    );
    expect(markdown.contentUrl).toBe("https://sponda.capital/pt/PETR4/graficos.md");
  });

  it("types every distribution as a DataDownload", async () => {
    for (const entry of (await dataset("PETR4", "en")).distribution) {
      expect(entry["@type"]).toBe("DataDownload");
    }
  });
});

describe("tab pages carry their own title and description", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(async () => ({
      ok: true,
      json: async () => ({ name: "Banco do Brasil", sector: "Finance" }),
    })));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("names the tab in the title so the four company pages stop sharing one", async () => {
    const root = await generateTickerMetadata("BBAS3", "en");
    const charts = await generateTickerMetadata("BBAS3", "en", "charts");
    const fundamentals = await generateTickerMetadata("BBAS3", "en", "fundamentals");
    const compare = await generateTickerMetadata("BBAS3", "en", "compare");

    expect(charts.title).toBe("Banco do Brasil (BBAS3) · Charts · Sponda");
    expect(fundamentals.title).toBe("Banco do Brasil (BBAS3) · Fundamentals · Sponda");
    expect(compare.title).toBe("Banco do Brasil (BBAS3) · Compare · Sponda");
    expect(new Set([root.title, charts.title, fundamentals.title, compare.title]).size).toBe(4);
  });

  it("describes what the tab shows, in the page's locale", async () => {
    const root = await generateTickerMetadata("BBAS3", "pt");
    const charts = await generateTickerMetadata("BBAS3", "pt", "graficos");
    const compare = await generateTickerMetadata("BBAS3", "pt", "comparar");

    expect(charts.description).toContain("Gráficos de Banco do Brasil (BBAS3)");
    expect(compare.description).toContain("Compare Banco do Brasil (BBAS3)");
    expect(charts.description).not.toBe(root.description);
    expect(compare.description).not.toBe(root.description);
  });

  it("mirrors the tab title and description into Open Graph and Twitter", async () => {
    const charts = await generateTickerMetadata("BBAS3", "en", "charts");

    expect(charts.openGraph?.title).toBe(charts.title);
    expect(charts.openGraph?.description).toBe(charts.description);
    expect(charts.twitter?.title).toBe(charts.title);
  });
});

describe("title length", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  function stubCompanyName(name: string) {
    vi.stubGlobal("fetch", vi.fn(async () => ({
      ok: true,
      json: async () => ({ name, sector: "Utilities" }),
    })));
  }

  it("keeps a short company name in the full form", async () => {
    stubCompanyName("Banco do Brasil");
    const metadata = await generateTickerMetadata("BBAS3", "en");
    expect(metadata.title).toBe("Banco do Brasil (BBAS3) · Fundamental Indicators · Sponda");
  });

  it("drops the generic suffix before a long company name overflows the SERP", async () => {
    stubCompanyName("Cia Saneamento Basico EST São Paulo");
    const metadata = await generateTickerMetadata("SBSP3", "en");

    expect(metadata.title).toBe("Cia Saneamento Basico EST São Paulo (SBSP3) · Sponda");
    expect((metadata.title as string).length).toBeLessThanOrEqual(MAX_TITLE_LENGTH);
  });

  it("falls back to the ticker alone when even the bare name is too long", async () => {
    stubCompanyName("Companhia de Saneamento Basico do Estado de Sao Paulo SABESP");
    const metadata = await generateTickerMetadata("SBSP3", "en");

    expect(metadata.title).toBe("SBSP3 · Fundamental Indicators · Sponda");
  });

  it("applies the same cap to tab titles", async () => {
    stubCompanyName("Cia Saneamento Basico EST São Paulo");
    const metadata = await generateTickerMetadata("SBSP3", "en", "fundamentals");

    expect((metadata.title as string).length).toBeLessThanOrEqual(MAX_TITLE_LENGTH);
    expect(metadata.title).toContain("Fundamentals");
  });
});

describe("hreflang alternates", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(async () => ({
      ok: true,
      json: async () => ({ name: "Petrobras", sector: "Energy" }),
    })));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("never advertises a noindex locale as an alternate", async () => {
    const metadata = await generateTickerMetadata("PETR4", "en");
    const languages = metadata.alternates?.languages as Record<string, string>;

    expect(Object.keys(languages)).not.toContain("zh");
    expect(languages["pt-BR"]).toBe("https://sponda.capital/pt/PETR4");
    expect(languages["x-default"]).toBe("https://sponda.capital/en/PETR4");
  });
});

describe("Dataset name", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(async () => ({
      ok: true,
      json: async () => ({ name: "Banco do Brasil", sector: "Finance" }),
    })));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("joins the suffix and the company with a single separator", async () => {
    const metadata = await generateTickerMetadata("BBAS3", "en");
    const schemas = JSON.parse(metadata.other?.["structured-data"] as string);
    const dataset = schemas.find((s: { "@type": string }) => s["@type"] === "Dataset");

    expect(dataset.name).toBe("Fundamental Indicators · Banco do Brasil (BBAS3)");
    expect(dataset.name).not.toMatch(/\s{2}/);
  });
});

describe("generateScreenerMetadata", () => {
  it("is canonical on its own URL, not the locale home", () => {
    const metadata = generateScreenerMetadata("en");
    expect(metadata.alternates?.canonical).toBe("https://sponda.capital/en/screener");
  });

  it("has a title and description that are not the home page's", () => {
    const metadata = generateScreenerMetadata("en");
    expect(metadata.title).toBe("Stock Screener · Sponda");
    expect(metadata.description).toContain("PE10");
    expect(metadata.openGraph?.url).toBe("https://sponda.capital/en/screener");
  });

  it("cross-links the indexable locales' screeners, and only those", () => {
    const languages = generateScreenerMetadata("pt").alternates?.languages as Record<string, string>;
    expect(languages["pt-BR"]).toBe("https://sponda.capital/pt/screener");
    expect(languages["en"]).toBe("https://sponda.capital/en/screener");
    expect(languages["x-default"]).toBe("https://sponda.capital/en/screener");
    expect(Object.keys(languages)).not.toContain("zh");
  });

  it("is localized", () => {
    expect(generateScreenerMetadata("pt").title).toBe("Filtro de Ações · Sponda");
    expect(generateScreenerMetadata("de").title).toBe("Aktien-Screener · Sponda");
  });
});
