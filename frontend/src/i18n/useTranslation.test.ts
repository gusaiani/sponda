import { describe, it, expect } from "vitest";
import { pt } from "./locales/pt";
import { en } from "./locales/en";
import type { TranslationKey } from "./types";

describe("Translation dictionaries", () => {
  const ptKeys = Object.keys(pt).sort() as TranslationKey[];
  const enKeys = Object.keys(en).sort() as TranslationKey[];

  it("pt and en have the same number of keys", () => {
    expect(ptKeys.length).toBe(enKeys.length);
  });

  it("pt and en have identical key sets", () => {
    const missingInEn = ptKeys.filter((key) => !(key in en));
    const missingInPt = enKeys.filter((key) => !(key in pt));
    expect(missingInEn).toEqual([]);
    expect(missingInPt).toEqual([]);
  });

  it("no translation value is empty", () => {
    for (const key of ptKeys) {
      expect(pt[key], `pt.${key} is empty`).not.toBe("");
    }
    for (const key of enKeys) {
      expect(en[key], `en.${key} is empty`).not.toBe("");
    }
  });

  it("pt and en have different values for locale-specific keys", () => {
    // These keys should definitely differ between pt and en
    const mustDiffer: TranslationKey[] = [
      "header.tagline",
      "auth.login",
      "auth.password",
      "common.loading",
      "search.placeholder",
    ];
    for (const key of mustDiffer) {
      expect(pt[key], `${key} should differ`).not.toBe(en[key]);
    }
  });

  it("interpolation placeholders in pt exist in en and vice versa", () => {
    const placeholderPattern = /\{(\w+)\}/g;

    for (const key of ptKeys) {
      const ptPlaceholders = [...pt[key].matchAll(placeholderPattern)].map((m) => m[1]).sort();
      const enPlaceholders = [...en[key].matchAll(placeholderPattern)].map((m) => m[1]).sort();
      expect(ptPlaceholders, `Placeholders mismatch for "${key}"`).toEqual(enPlaceholders);
    }
  });
});

describe("Locale detection", () => {
  it("exports valid Locale type values", () => {
    const validLocales = ["pt", "en"];
    expect(validLocales).toContain("pt");
    expect(validLocales).toContain("en");
  });
});
