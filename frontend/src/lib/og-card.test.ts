import { describe, it, expect, vi, afterEach } from "vitest";
import {
  OG_CARD_WIDTH,
  OG_CARD_HEIGHT,
  MAX_COMPANY_NAME_LENGTH,
  MISSING_VALUE,
  ogImageUrlForTicker,
  tickerFromOgImageParam,
  buildOgCardModel,
  fetchOgCardData,
  siteOgArtworkForLocale,
  siteOgImageUrlForLocale,
  siteOgArtworkFromParam,
} from "./og-card";

/** One row of `/api/tickers/VULC3/indicators/`, trimmed to what the card reads. */
const VULCABRAS_SNAPSHOT = {
  symbol: "VULC3",
  name: "Vulcabras",
  sector: "Consumer Non-Durables",
  pe10: 22.81,
  pfcf10: 62.67,
  peg: 0.78,
  debt_to_equity: 0.14,
};

describe("card dimensions", () => {
  it("matches the 1200x630 the meta tags advertise", () => {
    expect(OG_CARD_WIDTH).toBe(1200);
    expect(OG_CARD_HEIGHT).toBe(630);
  });
});

describe("ogImageUrlForTicker", () => {
  it("builds a per-locale, per-ticker path under /og/", () => {
    expect(ogImageUrlForTicker("pt", "VULC3")).toBe("/og/pt/VULC3.png");
    expect(ogImageUrlForTicker("en", "AAPL")).toBe("/og/en/AAPL.png");
  });

  it("uppercases the ticker so one company maps to one cache entry", () => {
    expect(ogImageUrlForTicker("pt", "vulc3")).toBe("/og/pt/VULC3.png");
  });
});

describe("tickerFromOgImageParam", () => {
  it("strips the .png extension", () => {
    expect(tickerFromOgImageParam("VULC3.png")).toBe("VULC3");
  });

  it("uppercases the ticker", () => {
    expect(tickerFromOgImageParam("vulc3.png")).toBe("VULC3");
  });

  it("rejects a param with no .png extension so one image has one URL", () => {
    expect(tickerFromOgImageParam("VULC3")).toBeNull();
  });

  it("rejects anything that is not a plain ticker", () => {
    expect(tickerFromOgImageParam("../secrets.png")).toBeNull();
    expect(tickerFromOgImageParam("a b.png")).toBeNull();
    expect(tickerFromOgImageParam(".png")).toBeNull();
    expect(tickerFromOgImageParam("VERYLONGTICKERNAME123.png")).toBeNull();
  });

  it("accepts the dot and hyphen real tickers use", () => {
    expect(tickerFromOgImageParam("BRK-B.png")).toBe("BRK-B");
    expect(tickerFromOgImageParam("BBAS3.SA.png")).toBe("BBAS3.SA");
  });
});

describe("buildOgCardModel", () => {
  it("uses the company name and translated sector", () => {
    const model = buildOgCardModel({
      ticker: "VULC3",
      locale: "pt",
      name: "Vulcabras",
      sector: "Consumer Non-Durables",
      snapshot: VULCABRAS_SNAPSHOT,
    });

    expect(model.companyName).toBe("Vulcabras");
    expect(model.ticker).toBe("VULC3");
    expect(model.sector).toBe("Bens de Consumo Não Duráveis");
  });

  it("falls back to the ticker when the company name is unknown", () => {
    const model = buildOgCardModel({
      ticker: "VULC3",
      locale: "pt",
      name: null,
      sector: null,
      snapshot: null,
    });

    expect(model.companyName).toBe("VULC3");
    expect(model.sector).toBe("");
  });

  it("puts the ticker and sector on the subtitle line", () => {
    const model = buildOgCardModel({
      ticker: "VULC3",
      locale: "pt",
      name: "Vulcabras",
      sector: "Consumer Non-Durables",
      snapshot: VULCABRAS_SNAPSHOT,
    });

    expect(model.subtitle).toBe("VULC3 · Bens de Consumo Não Duráveis");
  });

  it("drops the sector from the subtitle when the API has none", () => {
    const model = buildOgCardModel({
      ticker: "VULC3", locale: "en", name: "Vulcabras", sector: null, snapshot: null,
    });

    expect(model.subtitle).toBe("VULC3");
  });

  it("leaves the subtitle empty rather than echoing the headline", () => {
    // With no company name the headline is already the ticker, so repeating
    // it underneath just prints the same word twice.
    const model = buildOgCardModel({
      ticker: "NOSUCH", locale: "en", name: null, sector: null, snapshot: null,
    });

    expect(model.companyName).toBe("NOSUCH");
    expect(model.subtitle).toBe("");
  });

  it("still shows the sector when the company name is unknown", () => {
    const model = buildOgCardModel({
      ticker: "NOSUCH", locale: "en", name: null, sector: "Technology", snapshot: null,
    });

    expect(model.subtitle).toBe("NOSUCH · Technology");
  });

  it("truncates a company name too long to fit the card", () => {
    const longName = "A".repeat(MAX_COMPANY_NAME_LENGTH + 20);
    const model = buildOgCardModel({
      ticker: "LONG3",
      locale: "en",
      name: longName,
      sector: null,
      snapshot: null,
    });

    expect(model.companyName.length).toBeLessThanOrEqual(MAX_COMPANY_NAME_LENGTH + 1);
    expect(model.companyName.endsWith("…")).toBe(true);
  });

  it("renders the four headline indicators the snapshot can always answer", () => {
    // Earnings CAGR only exists on the live quote payload, which sits behind
    // the lookup quota. Debt/Equity is on the snapshot for 86% of companies.
    const model = buildOgCardModel({
      ticker: "VULC3",
      locale: "en",
      name: "Vulcabras",
      sector: "Consumer Non-Durables",
      snapshot: VULCABRAS_SNAPSHOT,
    });

    expect(model.indicators.map((indicator) => indicator.label)).toEqual([
      "PE10",
      "PFCF10",
      "PEG",
      "D/E",
    ]);
  });

  it("labels the leverage tile in the card's language", () => {
    const model = buildOgCardModel({
      ticker: "VULC3",
      locale: "pt",
      name: "Vulcabras",
      sector: null,
      snapshot: VULCABRAS_SNAPSHOT,
    });

    expect(model.indicators[3].label).toBe("Dív/PL");
  });

  it("formats values with the locale's decimal separator", () => {
    const portuguese = buildOgCardModel({
      ticker: "VULC3", locale: "pt", name: "Vulcabras", sector: null, snapshot: VULCABRAS_SNAPSHOT,
    });
    const english = buildOgCardModel({
      ticker: "VULC3", locale: "en", name: "Vulcabras", sector: null, snapshot: VULCABRAS_SNAPSHOT,
    });

    expect(portuguese.indicators[0].value).toBe("22,8");
    expect(english.indicators[0].value).toBe("22.8");
  });

  it("renders debt to equity as a two-decimal ratio", () => {
    const model = buildOgCardModel({
      ticker: "VULC3", locale: "en", name: "Vulcabras", sector: null, snapshot: VULCABRAS_SNAPSHOT,
    });

    expect(model.indicators[3].value).toBe("0.14");
  });

  it("shows the product's missing-value marker for indicators the snapshot lacks", () => {
    const model = buildOgCardModel({
      ticker: "VULC3",
      locale: "en",
      name: "Vulcabras",
      sector: null,
      snapshot: { ...VULCABRAS_SNAPSHOT, peg: null, debt_to_equity: null },
    });

    expect(model.indicators[2].value).toBe(MISSING_VALUE);
    expect(model.indicators[3].value).toBe(MISSING_VALUE);
  });

  it("keeps every indicator slot even with no snapshot at all, so the layout is stable", () => {
    const model = buildOgCardModel({
      ticker: "VULC3", locale: "en", name: "Vulcabras", sector: null, snapshot: null,
    });

    expect(model.indicators).toHaveLength(4);
    expect(model.indicators.every((indicator) => indicator.value === MISSING_VALUE)).toBe(true);
  });

  it("uses the locale's tagline", () => {
    expect(buildOgCardModel({
      ticker: "VULC3", locale: "pt", name: null, sector: null, snapshot: null,
    }).tagline).toBe("Para investidores em valor");

    expect(buildOgCardModel({
      ticker: "AAPL", locale: "de", name: null, sector: null, snapshot: null,
    }).tagline).toBe("Für Value-Investoren");
  });

  it("falls back to the English tagline for zh, whose glyphs the card font lacks", () => {
    const model = buildOgCardModel({
      ticker: "VULC3", locale: "zh", name: null, sector: null, snapshot: null,
    });

    expect(model.tagline).toBe("For value investors");
  });
});

describe("fetchOgCardData", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("reads the quota-free snapshot endpoint, never /api/quote/", async () => {
    // /api/quote/ sits behind the daily lookup cap, scoped by client IP. The
    // Next server is one IP, so every card on the site shared twenty
    // lookups a day and then rendered N/A in every slot.
    const fetchMock = vi.fn(async (url: string) => ({
      ok: true,
      json: async () => (url.includes("/indicators/")
        ? VULCABRAS_SNAPSHOT
        : { name: "Vulcabras", sector: "Consumer Non-Durables" }),
    }));
    vi.stubGlobal("fetch", fetchMock);

    const data = await fetchOgCardData("VULC3");

    const requestedUrls = fetchMock.mock.calls.map(([url]) => url);
    expect(requestedUrls).toContain("http://localhost:8710/api/tickers/VULC3/indicators/");
    expect(requestedUrls.some((url) => url.includes("/api/quote/"))).toBe(false);
    expect(data.name).toBe("Vulcabras");
    expect(data.sector).toBe("Consumer Non-Durables");
    expect(data.snapshot?.pe10).toBe(22.81);
  });

  it("still returns the company identity when there is no snapshot row", async () => {
    // Funds, ETFs and companies with no market cap have a ticker and no
    // snapshot; the endpoint answers 404 for them.
    vi.stubGlobal("fetch", vi.fn(async (url: string) => (url.includes("/indicators/")
      ? { ok: false, status: 404, json: async () => ({}) }
      : { ok: true, json: async () => ({ name: "Vulcabras", sector: "Consumer Non-Durables" }) })));

    const data = await fetchOgCardData("VULC3");

    expect(data.name).toBe("Vulcabras");
    expect(data.sector).toBe("Consumer Non-Durables");
    expect(data.snapshot).toBeNull();
  });

  it("takes the identity from the snapshot when the ticker endpoint fails", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => (url.includes("/indicators/")
      ? { ok: true, json: async () => VULCABRAS_SNAPSHOT }
      : { ok: false, status: 500, json: async () => ({}) })));

    const data = await fetchOgCardData("VULC3");

    expect(data.name).toBe("Vulcabras");
    expect(data.sector).toBe("Consumer Non-Durables");
  });

  it("resolves to empty data rather than throwing when the API is unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => {
      throw new Error("ECONNREFUSED");
    }));

    const data = await fetchOgCardData("VULC3");

    expect(data).toEqual({ name: null, sector: null, snapshot: null });
  });
});

describe("site card (pages with no company to render)", () => {
  it("serves Portuguese artwork to pt and English artwork to everyone else", () => {
    expect(siteOgArtworkForLocale("pt")).toBe("pt");
    expect(siteOgArtworkForLocale("en")).toBe("en");
    expect(siteOgArtworkForLocale("es")).toBe("en");
    expect(siteOgArtworkForLocale("zh")).toBe("en");
  });

  it("lives under /og/site/, a URL no social network has seen before", () => {
    expect(siteOgImageUrlForLocale("pt")).toBe("/og/site/pt.jpg");
    expect(siteOgImageUrlForLocale("en")).toBe("/og/site/en.jpg");
    expect(siteOgImageUrlForLocale("fr")).toBe("/og/site/en.jpg");
  });

  it("recovers the artwork from the route param and rejects anything else", () => {
    expect(siteOgArtworkFromParam("pt.jpg")).toBe("pt");
    expect(siteOgArtworkFromParam("en.jpg")).toBe("en");
    expect(siteOgArtworkFromParam("es.jpg")).toBeNull();
    expect(siteOgArtworkFromParam("en.png")).toBeNull();
    expect(siteOgArtworkFromParam("en")).toBeNull();
    expect(siteOgArtworkFromParam("../en.jpg")).toBeNull();
  });
});
