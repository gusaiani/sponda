import { describe, expect, it, vi, afterEach, beforeEach } from "vitest";
import sitemap from "./sitemap";
import { SUPPORTED_LOCALES } from "../lib/i18n-config";
import { getPopularSymbols } from "../utils/suggestedCompanies";
import { tabSlugForLocale } from "../utils/tabs";

const SITEMAP_LOCALES = ["pt", "en"];
const FAKE_LAST_UPDATED = "2026-04-22T10:30:00.000Z";

describe("sitemap", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ tickers: { last_updated: FAKE_LAST_UPDATED, stale: false } }),
    }));
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it("lists only pt and en locales in sitemap URLs, with hreflang for all locales", async () => {
    const entries = await sitemap();
    const urls = entries.map((entry) => entry.url);

    expect(urls).toContain("https://sponda.capital/en");
    expect(urls).toContain("https://sponda.capital/pt");
    expect(urls).toContain("https://sponda.capital/pt/screener");
    expect(urls).toContain("https://sponda.capital/en/screener");
    expect(urls).toContain("https://sponda.capital/pt/PETR4");
    expect(urls).toContain("https://sponda.capital/en/PETR4");
    expect(urls).toContain(`https://sponda.capital/en/AAPL/${tabSlugForLocale("en", "fundamentals")}`);

    // Other locales not in sitemap URLs
    expect(urls).not.toContain("https://sponda.capital/fr/screener");
    expect(urls).not.toContain("https://sponda.capital/it/PETR4/grafici");
    expect(urls).not.toContain("https://sponda.capital/de/AAPL/" + tabSlugForLocale("de", "fundamentals"));

    // Auth routes never in sitemap
    expect(urls).not.toContain("https://sponda.capital/en/login");
    expect(urls).not.toContain("https://sponda.capital/en/signup");
  });

  it("hreflang alternates include all supported locales", async () => {
    const entries = await sitemap();
    const homeEntry = entries.find((e) => e.url === "https://sponda.capital/en");
    const languages = homeEntry?.alternates?.languages as Record<string, string>;

    for (const locale of SUPPORTED_LOCALES) {
      const key = locale === "pt" ? "pt-BR" : locale;
      expect(languages[key]).toBe(`https://sponda.capital/${locale}`);
    }
    expect(languages["x-default"]).toBe("https://sponda.capital/en");
  });

  it("uses real lastModified from health endpoint", async () => {
    const entries = await sitemap();
    expect(entries[0]?.lastModified).toBe(FAKE_LAST_UPDATED);
  });

  it("falls back to current time when health endpoint fails", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-04-22T12:00:00.000Z"));
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network error")));

    const entries = await sitemap();
    expect(entries[0]?.lastModified).toBe("2026-04-22T12:00:00.000Z");
  });

  it("has correct entry count: 2 locales x (2 static + ticker*4 dynamic)", async () => {
    const entries = await sitemap();
    const curatedTickers = [...new Set([
      ...getPopularSymbols("brazil"),
      ...getPopularSymbols("us"),
      ...getPopularSymbols("europe"),
      ...getPopularSymbols("asia"),
    ])];

    expect(entries).toHaveLength((2 + curatedTickers.length * 4) * SITEMAP_LOCALES.length);
  });
});
