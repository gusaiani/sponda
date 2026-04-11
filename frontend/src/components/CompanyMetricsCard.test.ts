import { describe, it, expect } from "vitest";
import { buildMarketCapSeries, buildQuarterlyRatioSeries, formatYearsOfData } from "./CompanyMetricsCard";

describe("buildMarketCapSeries", () => {
  const priceHistory = [
    { date: "2024-01-02", adjustedClose: 10 },
    { date: "2024-01-03", adjustedClose: 11 },
    { date: "2024-01-04", adjustedClose: 12 },
    { date: "2024-01-05", adjustedClose: 13 },
    { date: "2024-01-08", adjustedClose: 14 },
    { date: "2024-01-09", adjustedClose: 15 },
    { date: "2024-01-10", adjustedClose: 16 },
    { date: "2024-01-11", adjustedClose: 17 },
    { date: "2024-01-12", adjustedClose: 18 },
    { date: "2024-01-15", adjustedClose: 19 },
  ];

  it("computes daily market cap from price × shares outstanding", () => {
    // marketCap = 200, currentPrice = 20 → shares = 10
    const result = buildMarketCapSeries(priceHistory, 200, 20, 10);
    expect(result.length).toBeGreaterThan(0);
    // First point: price 10 × shares 10 = 100
    expect(result[0].value).toBe(100);
    // Last point: price 19 × shares 10 = 190
    expect(result[result.length - 1].value).toBe(190);
  });

  it("returns empty array when priceHistory is empty", () => {
    const result = buildMarketCapSeries([], 200, 20, 10);
    expect(result).toEqual([]);
  });

  it("returns empty array when marketCap is null", () => {
    const result = buildMarketCapSeries(priceHistory, null, 20, 10);
    expect(result).toEqual([]);
  });

  it("returns empty array when currentPrice is zero", () => {
    const result = buildMarketCapSeries(priceHistory, 200, 0, 10);
    expect(result).toEqual([]);
  });

  it("uses yearTick field for year boundary ticks", () => {
    const result = buildMarketCapSeries(priceHistory, 200, 20, 10);
    expect(result[0]).toHaveProperty("yearTick");
    expect(result[0].yearTick).toBe("24");
  });

  it("filters by years parameter", () => {
    const mixedYears = [
      { date: "2020-06-01", adjustedClose: 5 },
      { date: "2023-06-01", adjustedClose: 8 },
      { date: "2024-06-01", adjustedClose: 10 },
    ];
    // years=1 means only current year backward
    const result = buildMarketCapSeries(mixedYears, 200, 20, 1);
    // Should filter out 2020 (4 years ago from 2024+)
    expect(result.every((p) => !p.label.startsWith("2020"))).toBe(true);
  });

  it("always includes the last data point", () => {
    const result = buildMarketCapSeries(priceHistory, 200, 20, 10);
    const lastPrice = priceHistory[priceHistory.length - 1];
    expect(result[result.length - 1].label).toBe(lastPrice.date);
  });
});

describe("buildQuarterlyRatioSeries", () => {
  const quarterlyRatios = [
    { date: "2023-03-31", debtToEquity: 0.5, liabilitiesToEquity: 1.0 },
    { date: "2023-06-30", debtToEquity: 0.6, liabilitiesToEquity: 1.1 },
    { date: "2023-09-30", debtToEquity: 0.7, liabilitiesToEquity: 1.2 },
    { date: "2023-12-31", debtToEquity: 0.8, liabilitiesToEquity: 1.3 },
    { date: "2024-03-31", debtToEquity: 0.55, liabilitiesToEquity: 1.05 },
    { date: "2024-06-30", debtToEquity: 0.65, liabilitiesToEquity: 1.15 },
    { date: "2024-09-30", debtToEquity: null, liabilitiesToEquity: 1.25 },
    { date: "2024-12-31", debtToEquity: 0.75, liabilitiesToEquity: 1.35 },
  ];

  it("builds series for debtToEquity field", () => {
    const result = buildQuarterlyRatioSeries(quarterlyRatios, "debtToEquity", 10);
    // Should exclude the null entry
    expect(result.length).toBe(7);
    expect(result[0].value).toBe(0.5);
    expect(result[0].label).toBe("2023-03-31");
  });

  it("builds series for liabilitiesToEquity field", () => {
    const result = buildQuarterlyRatioSeries(quarterlyRatios, "liabilitiesToEquity", 10);
    expect(result.length).toBe(8);
    expect(result[7].value).toBe(1.35);
  });

  it("filters by years parameter", () => {
    const result = buildQuarterlyRatioSeries(quarterlyRatios, "debtToEquity", 1);
    // Only 2024 data (current year is 2025+, startYear = currentYear - 1)
    expect(result.every((p) => p.label.startsWith("2024"))).toBe(true);
  });

  it("returns empty for empty input", () => {
    expect(buildQuarterlyRatioSeries([], "debtToEquity", 10)).toEqual([]);
  });

  it("includes yearTick field", () => {
    const result = buildQuarterlyRatioSeries(quarterlyRatios, "debtToEquity", 10);
    expect(result[0].yearTick).toBe("23");
    expect(result[4].yearTick).toBe("24");
  });
});

describe("formatYearsOfData", () => {
  it("returns single number when pe10 and pfcf10 years are equal", () => {
    expect(formatYearsOfData(10, 10)).toBe("10");
  });

  it("returns labeled format when pe10 and pfcf10 years differ", () => {
    expect(formatYearsOfData(7, 6)).toBe("L: 7 · FCL: 6");
  });

  it("handles zero values", () => {
    expect(formatYearsOfData(0, 0)).toBe("0");
  });

  it("handles different order (pfcf10 > pe10)", () => {
    expect(formatYearsOfData(5, 8)).toBe("L: 5 · FCL: 8");
  });
});
