import { describe, it, expect } from "vitest";
import { selectHomepageTickers, formatMarketCap } from "./HomepageCompanyCards";

const DEFAULT_TICKERS = [
  "PETR4", "VALE3", "ITUB4", "BBDC4", "BBAS3",
  "WEGE3", "ABEV3", "B3SA3",
];

describe("selectHomepageTickers", () => {
  it("returns default tickers when user is not authenticated", () => {
    const result = selectHomepageTickers({
      isAuthenticated: false,
      favoriteTickers: [],
      defaultTickers: DEFAULT_TICKERS,
      maxCards: 8,
    });
    expect(result).toEqual(DEFAULT_TICKERS);
  });

  it("returns default tickers when authenticated but no favorites", () => {
    const result = selectHomepageTickers({
      isAuthenticated: true,
      favoriteTickers: [],
      defaultTickers: DEFAULT_TICKERS,
      maxCards: 8,
    });
    expect(result).toEqual(DEFAULT_TICKERS);
  });

  it("returns favorites when authenticated with favorites", () => {
    const result = selectHomepageTickers({
      isAuthenticated: true,
      favoriteTickers: ["WEGE3", "ABEV3", "RENT3"],
      defaultTickers: DEFAULT_TICKERS,
      maxCards: 8,
    });
    expect(result).toEqual(["WEGE3", "ABEV3", "RENT3"]);
  });

  it("caps at maxCards", () => {
    const result = selectHomepageTickers({
      isAuthenticated: true,
      favoriteTickers: [
        "A1", "A2", "A3", "A4", "A5",
        "A6", "A7", "A8", "A9", "A10",
      ],
      defaultTickers: DEFAULT_TICKERS,
      maxCards: 8,
    });
    expect(result).toHaveLength(8);
  });

  it("returns default tickers capped at maxCards", () => {
    const result = selectHomepageTickers({
      isAuthenticated: false,
      favoriteTickers: [],
      defaultTickers: DEFAULT_TICKERS,
      maxCards: 4,
    });
    expect(result).toHaveLength(4);
    expect(result).toEqual(["PETR4", "VALE3", "ITUB4", "BBDC4"]);
  });
});

describe("formatMarketCap", () => {
  it("returns null for null input", () => {
    expect(formatMarketCap(null, "", "pt")).toBeNull();
  });

  it("formats trillions as billions using locale separators (pt)", () => {
    const result = formatMarketCap(1.5e12, "", "pt");
    expect(result).toContain("1.500");
    expect(result).toContain("B");
    expect(result).toContain("R$");
  });

  it("formats trillions as billions using locale separators (en)", () => {
    const result = formatMarketCap(1.5e12, "AAPL", "en");
    expect(result).toContain("1,500");
    expect(result).toContain("B");
    expect(result).toContain("$");
  });

  it("formats billions with one decimal", () => {
    const result = formatMarketCap(45.3e9, "", "pt");
    expect(result).toContain("B");
    expect(result).toContain("R$");
  });

  it("formats millions", () => {
    const result = formatMarketCap(350e6, "", "pt");
    expect(result).toContain("M");
    expect(result).toContain("R$");
  });

  it("formats small values without suffix", () => {
    const result = formatMarketCap(50000, "", "pt");
    expect(result).toContain("R$");
    expect(result).not.toContain("B");
    expect(result).not.toContain("M");
  });
});
