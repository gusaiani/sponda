import { describe, it, expect } from "vitest";
import {
  detectLocaleFromHeader,
  NOINDEX_LOCALES,
  isNoindexLocale,
  robotsForLocale,
  INDEXABLE_LOCALES,
  SUPPORTED_LOCALES,
} from "./i18n-config";

describe("detectLocaleFromHeader", () => {
  it("returns en when header is null", () => {
    expect(detectLocaleFromHeader(null)).toBe("en");
  });

  it("returns en when header is empty", () => {
    expect(detectLocaleFromHeader("")).toBe("en");
  });

  it("detects Portuguese", () => {
    expect(detectLocaleFromHeader("pt-BR,pt;q=0.9,en;q=0.8")).toBe("pt");
  });

  it("detects Spanish", () => {
    expect(detectLocaleFromHeader("es-ES,es;q=0.9")).toBe("es");
  });

  it("detects Chinese", () => {
    expect(detectLocaleFromHeader("zh-CN,zh;q=0.9")).toBe("zh");
  });

  it("detects French", () => {
    expect(detectLocaleFromHeader("fr-FR,fr;q=0.9,en;q=0.8")).toBe("fr");
  });

  it("detects German", () => {
    expect(detectLocaleFromHeader("de-DE,de;q=0.9")).toBe("de");
  });

  it("detects Italian", () => {
    expect(detectLocaleFromHeader("it-IT,it;q=0.9")).toBe("it");
  });

  it("falls back to en for unsupported language", () => {
    expect(detectLocaleFromHeader("ja-JP,ja;q=0.9")).toBe("en");
  });

  it("respects priority order — first matching language wins", () => {
    expect(detectLocaleFromHeader("ja-JP,fr;q=0.9,de;q=0.8")).toBe("fr");
  });

  it("matches en explicitly when present (not just default)", () => {
    expect(detectLocaleFromHeader("en-US,en;q=0.9")).toBe("en");
  });

  it("is case-insensitive", () => {
    expect(detectLocaleFromHeader("FR-FR,FR;q=0.9")).toBe("fr");
  });
});

describe("noindex locale policy", () => {
  it("marks zh as noindex (scraper-dominated, no real audience)", () => {
    expect(NOINDEX_LOCALES.has("zh")).toBe(true);
    expect(isNoindexLocale("zh")).toBe(true);
  });

  it("keeps the primary locales indexable", () => {
    for (const locale of ["pt", "en"] as const) {
      expect(isNoindexLocale(locale)).toBe(false);
    }
  });

  it("robotsForLocale returns noindex for zh and index for others", () => {
    expect(robotsForLocale("zh")).toBe("noindex, follow");
    expect(robotsForLocale("pt")).toBe("index, follow");
    expect(robotsForLocale("en")).toBe("index, follow");
  });

  it("INDEXABLE_LOCALES is every supported locale minus the noindex set", () => {
    expect(INDEXABLE_LOCALES).not.toContain("zh");
    for (const locale of SUPPORTED_LOCALES) {
      expect(INDEXABLE_LOCALES.includes(locale)).toBe(!isNoindexLocale(locale));
    }
  });
});
