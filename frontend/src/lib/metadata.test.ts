import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { getOgImageUrl, generateTickerMetadata } from "./metadata";

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

    expect(metadata.openGraph?.type).toBe("website");
  });

  it("points Open Graph and Twitter at the same absolute image URL", async () => {
    const metadata = await generateTickerMetadata("VULC3", "pt");
    const expectedUrl = "https://sponda.capital/images/sponda-og-v2.jpg";

    const openGraphImages = metadata.openGraph?.images as Array<{ url: string }>;
    expect(openGraphImages[0].url).toBe(expectedUrl);
    expect(metadata.twitter?.images).toEqual([expectedUrl]);
  });

  it("declares the image MIME type and alt text for the card renderer", async () => {
    const metadata = await generateTickerMetadata("VULC3", "pt");

    const openGraphImages = metadata.openGraph?.images as Array<{
      type: string;
      alt: string;
      width: number;
      height: number;
    }>;
    expect(openGraphImages[0].type).toBe("image/jpeg");
    expect(openGraphImages[0].alt).toContain("Sponda");
    expect(openGraphImages[0].width).toBe(1200);
    expect(openGraphImages[0].height).toBe(630);
  });
});
