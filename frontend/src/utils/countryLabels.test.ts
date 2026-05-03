import { describe, it, expect } from "vitest";
import { translateCountry } from "./countryLabels";

describe("translateCountry", () => {
  it("returns the Portuguese name for known ISO codes in pt", () => {
    expect(translateCountry("BR", "pt")).toBe("Brasil");
    expect(translateCountry("US", "pt")).toBe("Estados Unidos");
    expect(translateCountry("TW", "pt")).toBe("Taiwan");
    expect(translateCountry("GB", "pt")).toBe("Reino Unido");
  });

  it("returns the English name for known ISO codes in en", () => {
    expect(translateCountry("BR", "en")).toBe("Brazil");
    expect(translateCountry("US", "en")).toBe("United States");
    expect(translateCountry("GB", "en")).toBe("United Kingdom");
  });

  it("falls back to English for locales without a translation table", () => {
    expect(translateCountry("BR", "fr")).toBe("Brazil");
    expect(translateCountry("US", "de")).toBe("United States");
  });

  it("falls back to the raw ISO code when the country is unknown", () => {
    expect(translateCountry("ZZ", "pt")).toBe("ZZ");
    expect(translateCountry("ZZ", "en")).toBe("ZZ");
  });

  it("normalizes lowercase ISO codes", () => {
    expect(translateCountry("br", "pt")).toBe("Brasil");
    expect(translateCountry("us", "en")).toBe("United States");
  });
});
