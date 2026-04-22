import { describe, expect, it, vi, afterEach } from "vitest";
import sitemap from "./sitemap";
import { SUPPORTED_LOCALES } from "../lib/i18n-config";
import { getPopularSymbols } from "../utils/suggestedCompanies";
import { tabSlugForLocale } from "../utils/tabs";

describe("sitemap", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("lists only localized discovery and curated company routes", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-04-22T12:00:00.000Z"));

    const entries = await sitemap();
    const urls = entries.map((entry) => entry.url);
    const curatedTickers = [...new Set([
      ...getPopularSymbols("brazil"),
      ...getPopularSymbols("us"),
      ...getPopularSymbols("europe"),
      ...getPopularSymbols("asia"),
    ])];

    expect(urls).toContain("https://sponda.capital/en");
    expect(urls).toContain("https://sponda.capital/fr/screener");
    expect(urls).toContain("https://sponda.capital/pt/PETR4");
    expect(urls).toContain("https://sponda.capital/it/PETR4/grafici");
    expect(urls).toContain(`https://sponda.capital/de/AAPL/${tabSlugForLocale("de", "fundamentals")}`);
    expect(urls).not.toContain("https://sponda.capital/en/login");
    expect(urls).not.toContain("https://sponda.capital/en/signup");

    expect(entries).toHaveLength((2 + curatedTickers.length * 4) * SUPPORTED_LOCALES.length);
    expect(entries[0]?.lastModified).toBe("2026-04-22T12:00:00.000Z");
  });
});
