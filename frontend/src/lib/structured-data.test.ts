import { describe, it, expect } from "vitest";
import { buildSiteStructuredData } from "./structured-data";

describe("buildSiteStructuredData", () => {
  it("describes the site as a WebSite and its publisher as an Organization", () => {
    const schemas = buildSiteStructuredData("en");
    const types = schemas.map((schema) => schema["@type"]);

    expect(types).toEqual(["WebSite", "Organization"]);
  });

  it("does not claim to be a software application, which Google will not accept without a rating", () => {
    // Google's SoftwareApplication rich result requires aggregateRating or
    // review. We have neither, so every page carrying WebApplication failed
    // structured-data validation.
    const schemas = buildSiteStructuredData("en");
    for (const schema of schemas) {
      expect(schema["@type"]).not.toMatch(/Application$/);
      expect(schema).not.toHaveProperty("offers");
    }
  });

  it("names the site, its URL and the page language on the WebSite entry", () => {
    const [website] = buildSiteStructuredData("pt");

    expect(website).toMatchObject({
      "@context": "https://schema.org",
      name: "Sponda",
      url: "https://sponda.capital",
      inLanguage: "pt-BR",
    });
    expect(typeof website.description).toBe("string");
    expect((website.description as string).length).toBeGreaterThan(20);
  });

  it("localizes the description", () => {
    const [english] = buildSiteStructuredData("en");
    const [german] = buildSiteStructuredData("de");
    expect(english.description).not.toBe(german.description);
  });

  it("gives the Organization a logo so the entry is complete", () => {
    const [, organization] = buildSiteStructuredData("en");

    expect(organization).toMatchObject({
      name: "Sponda",
      url: "https://sponda.capital",
      logo: "https://sponda.capital/sponda-logo-2026-03-20.png",
    });
  });
});
