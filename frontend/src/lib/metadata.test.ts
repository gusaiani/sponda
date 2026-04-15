import { describe, it, expect } from "vitest";
import { getOgImageUrl } from "./metadata";

describe("getOgImageUrl", () => {
  it("returns the Portuguese OG image for pt", () => {
    expect(getOgImageUrl("pt")).toBe("/images/sponda-og.jpg");
  });

  it("returns the English OG image for en", () => {
    expect(getOgImageUrl("en")).toBe("/images/sponda-og-en.jpg");
  });

  it("returns the English OG image for all other supported locales", () => {
    expect(getOgImageUrl("es")).toBe("/images/sponda-og-en.jpg");
    expect(getOgImageUrl("zh")).toBe("/images/sponda-og-en.jpg");
    expect(getOgImageUrl("fr")).toBe("/images/sponda-og-en.jpg");
    expect(getOgImageUrl("de")).toBe("/images/sponda-og-en.jpg");
    expect(getOgImageUrl("it")).toBe("/images/sponda-og-en.jpg");
  });
});
