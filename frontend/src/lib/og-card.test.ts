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
} from "./og-card";

const VULCABRAS_QUOTE = {
  name: "Vulcabras",
  pe10: 22.81,
  pe10Label: "PE15",
  pfcf10: 62.67,
  pfcf10Label: "PFCF15",
  peg: 0.78,
  earningsCAGR: 29.17,
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
      quote: VULCABRAS_QUOTE,
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
      quote: null,
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
      quote: VULCABRAS_QUOTE,
    });

    expect(model.subtitle).toBe("VULC3 · Bens de Consumo Não Duráveis");
  });

  it("drops the sector from the subtitle when the API has none", () => {
    const model = buildOgCardModel({
      ticker: "VULC3", locale: "en", name: "Vulcabras", sector: null, quote: null,
    });

    expect(model.subtitle).toBe("VULC3");
  });

  it("leaves the subtitle empty rather than echoing the headline", () => {
    // With no company name the headline is already the ticker, so repeating
    // it underneath just prints the same word twice.
    const model = buildOgCardModel({
      ticker: "NOSUCH", locale: "en", name: null, sector: null, quote: null,
    });

    expect(model.companyName).toBe("NOSUCH");
    expect(model.subtitle).toBe("");
  });

  it("still shows the sector when the company name is unknown", () => {
    const model = buildOgCardModel({
      ticker: "NOSUCH", locale: "en", name: null, sector: "Technology", quote: null,
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
      quote: null,
    });

    expect(model.companyName.length).toBeLessThanOrEqual(MAX_COMPANY_NAME_LENGTH + 1);
    expect(model.companyName.endsWith("…")).toBe(true);
  });

  it("renders the four headline indicators with the API's own window labels", () => {
    const model = buildOgCardModel({
      ticker: "VULC3",
      locale: "pt",
      name: "Vulcabras",
      sector: "Consumer Non-Durables",
      quote: VULCABRAS_QUOTE,
    });

    expect(model.indicators.map((indicator) => indicator.label)).toEqual([
      "PE15",
      "PFCF15",
      "PEG",
      "CAGR",
    ]);
  });

  it("falls back to the 10-year labels when the API omits them", () => {
    const model = buildOgCardModel({
      ticker: "VULC3",
      locale: "en",
      name: "Vulcabras",
      sector: null,
      quote: { ...VULCABRAS_QUOTE, pe10Label: null, pfcf10Label: null },
    });

    expect(model.indicators[0].label).toBe("PE10");
    expect(model.indicators[1].label).toBe("PFCF10");
  });

  it("formats values with the locale's decimal separator", () => {
    const portuguese = buildOgCardModel({
      ticker: "VULC3", locale: "pt", name: "Vulcabras", sector: null, quote: VULCABRAS_QUOTE,
    });
    const english = buildOgCardModel({
      ticker: "VULC3", locale: "en", name: "Vulcabras", sector: null, quote: VULCABRAS_QUOTE,
    });

    expect(portuguese.indicators[0].value).toBe("22,8");
    expect(english.indicators[0].value).toBe("22.8");
  });

  it("renders the earnings CAGR as a percentage", () => {
    const model = buildOgCardModel({
      ticker: "VULC3", locale: "en", name: "Vulcabras", sector: null, quote: VULCABRAS_QUOTE,
    });

    expect(model.indicators[3].value).toBe("29.2%");
  });

  it("shows the product's missing-value marker for indicators the API could not compute", () => {
    const model = buildOgCardModel({
      ticker: "VULC3",
      locale: "en",
      name: "Vulcabras",
      sector: null,
      quote: { ...VULCABRAS_QUOTE, peg: null, earningsCAGR: null },
    });

    expect(model.indicators[2].value).toBe(MISSING_VALUE);
    expect(model.indicators[3].value).toBe(MISSING_VALUE);
  });

  it("keeps every indicator slot even with no quote at all, so the layout is stable", () => {
    const model = buildOgCardModel({
      ticker: "VULC3", locale: "en", name: "Vulcabras", sector: null, quote: null,
    });

    expect(model.indicators).toHaveLength(4);
    expect(model.indicators.every((indicator) => indicator.value === MISSING_VALUE)).toBe(true);
  });

  it("uses the locale's tagline", () => {
    expect(buildOgCardModel({
      ticker: "VULC3", locale: "pt", name: null, sector: null, quote: null,
    }).tagline).toBe("Para investidores em valor");

    expect(buildOgCardModel({
      ticker: "AAPL", locale: "de", name: null, sector: null, quote: null,
    }).tagline).toBe("Für Value-Investoren");
  });

  it("falls back to the English tagline for zh, whose glyphs the card font lacks", () => {
    const model = buildOgCardModel({
      ticker: "VULC3", locale: "zh", name: null, sector: null, quote: null,
    });

    expect(model.tagline).toBe("For value investors");
  });
});

describe("fetchOgCardData", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("combines the ticker and quote endpoints", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => ({
      ok: true,
      json: async () => (url.includes("/quote/")
        ? VULCABRAS_QUOTE
        : { name: "Vulcabras", sector: "Consumer Non-Durables" }),
    })));

    const data = await fetchOgCardData("VULC3");

    expect(data.name).toBe("Vulcabras");
    expect(data.sector).toBe("Consumer Non-Durables");
    expect(data.quote?.pe10).toBe(22.81);
  });

  it("still returns the company identity when the quote endpoint fails", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => (url.includes("/quote/")
      ? { ok: false, json: async () => ({}) }
      : { ok: true, json: async () => ({ name: "Vulcabras", sector: "Consumer Non-Durables" }) })));

    const data = await fetchOgCardData("VULC3");

    expect(data.name).toBe("Vulcabras");
    expect(data.quote).toBeNull();
  });

  it("resolves to empty data rather than throwing when the API is unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => {
      throw new Error("ECONNREFUSED");
    }));

    const data = await fetchOgCardData("VULC3");

    expect(data).toEqual({ name: null, sector: null, quote: null });
  });
});
