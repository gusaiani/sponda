import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { getOgImageUrl, generateTickerMetadata } from "./metadata";

describe("getOgImageUrl", () => {
  it("returns the Portuguese site card for pt", () => {
    expect(getOgImageUrl("pt")).toBe("/og/site/pt.jpg");
  });

  it("returns the English site card for en", () => {
    expect(getOgImageUrl("en")).toBe("/og/site/en.jpg");
  });

  it("returns the English site card for all other supported locales", () => {
    expect(getOgImageUrl("es")).toBe("/og/site/en.jpg");
    expect(getOgImageUrl("zh")).toBe("/og/site/en.jpg");
    expect(getOgImageUrl("fr")).toBe("/og/site/en.jpg");
    expect(getOgImageUrl("de")).toBe("/og/site/en.jpg");
    expect(getOgImageUrl("it")).toBe("/og/site/en.jpg");
  });

  it("never points at the static /images/ files, whose URLs X has already given up on", () => {
    expect(getOgImageUrl("pt")).not.toContain("/images/");
    expect(getOgImageUrl("en")).not.toContain("/images/");
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
  it("uses the site card route, since there is no company to render", () => {
    expect(getOgImageUrl("pt")).toBe("/og/site/pt.jpg");
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
