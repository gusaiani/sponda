import { describe, it, expect } from "vitest";
import {
  computeTrailingPERatios,
  augmentWithPERatios,
  type TrailingRatioSource,
} from "./FundamentalsTab";
import { formatNumber } from "../utils/format";
import type { FundamentalsYear } from "../hooks/useFundamentals";

function makeYear(
  year: number,
  overrides: Partial<FundamentalsYear> = {},
): FundamentalsYear {
  return {
    year,
    quarters: 4,
    balanceSheetDate: null,
    marketCap: null,
    marketCapAdjusted: null,
    totalDebt: null,
    totalLease: null,
    debtExLease: null,
    debtExLeaseAdjusted: null,
    totalLiabilities: null,
    totalLiabilitiesAdjusted: null,
    stockholdersEquity: null,
    stockholdersEquityAdjusted: null,
    currentAssets: null,
    currentLiabilities: null,
    debtToEquity: null,
    liabilitiesToEquity: null,
    currentRatio: null,
    revenue: null,
    revenueAdjusted: null,
    netIncome: null,
    netIncomeAdjusted: null,
    fcf: null,
    fcfAdjusted: null,
    operatingCashFlow: null,
    operatingCashFlowAdjusted: null,
    dividendsPaid: null,
    dividendsAdjusted: null,
    ipcaFactor: 1,
    ...overrides,
  };
}

/** Build a quote-payload-like source from per-year period values.
 *  `periodValues[year]` lists that year's filings, oldest first. */
function makeSource(
  periodValues: Record<number, number[]>,
  periodsPerYear: 1 | 2 | 4 = 4,
): TrailingRatioSource {
  const yearsDescending = Object.keys(periodValues)
    .map(Number)
    .sort((a, b) => b - a);
  const endDateFor = (year: number, index: number, count: number): string => {
    if (periodsPerYear === 2) return `${year}-${index === 0 && count > 1 ? "06-30" : "12-31"}`;
    if (periodsPerYear === 1) return `${year}-12-31`;
    return `${year}-${String((index + 1) * 3).padStart(2, "0")}-30`;
  };
  return {
    pe10PeriodsPerYear: periodsPerYear,
    pfcf10PeriodsPerYear: periodsPerYear,
    pe10CalculationDetails: yearsDescending.map((year) => ({
      year,
      ipcaFactor: 1,
      quarters: periodValues[year].length,
      quarterlyDetail: periodValues[year].map((value, index) => ({
        end_date: endDateFor(year, index, periodValues[year].length),
        net_income: value,
      })),
    })),
    pfcf10CalculationDetails: yearsDescending.map((year) => ({
      year,
      ipcaFactor: 1,
      quarters: periodValues[year].length,
      quarterlyDetail: periodValues[year].map((value, index) => ({
        end_date: endDateFor(year, index, periodValues[year].length),
        fcf: value / 2,
      })),
    })),
  };
}

describe("computeTrailingPERatios", () => {
  it("computes each year's ratio from the trailing window anchored at that year", () => {
    // Every year earns 100 (4 × 25). Market caps differ per year, so the
    // ratio tracks the historical market cap over the same 100 average.
    const source = makeSource({
      2020: [25, 25, 25, 25],
      2021: [25, 25, 25, 25],
      2022: [25, 25, 25, 25],
      2023: [25, 25, 25, 25],
      2024: [25, 25, 25, 25],
    });
    const rows = [
      makeYear(2024, { marketCapAdjusted: 500 }),
      makeYear(2022, { marketCapAdjusted: 300 }),
    ];
    const result = computeTrailingPERatios(rows, source, 3);
    expect(result.get(2024)!.pe).toBe(5.0);
    // 2022's window is 2020-2022 — anchored at 2022, not at the latest year.
    expect(result.get(2022)!.pe).toBe(3.0);
  });

  it("weights a partial current year by its filings instead of counting it as a full year", () => {
    // 2026 has only Q1 ($10); 2023-2025 earn $40 each. The 3-year window
    // anchored at 2026 must trail into 2023 for 12 full quarters:
    // (10 + 40 + 40 + 30) ÷ 3 = 40 → PE = 400/40 = 10.
    // The old calendar-year average said (10+40+40)/3 = 30 → PE 13.3.
    const source = makeSource({
      2023: [10, 10, 10, 10],
      2024: [10, 10, 10, 10],
      2025: [10, 10, 10, 10],
      2026: [10],
    });
    const rows = [makeYear(2026, { quarters: 1, marketCapAdjusted: 400 })];
    const result = computeTrailingPERatios(rows, source, 3);
    expect(result.get(2026)!.pe).toBe(10);
  });

  it("handles semi-annual reporters: an N-year window is N×2 filings", () => {
    // RIO-style: 2 filings per year worth $10 each → $20/year average.
    const source = makeSource(
      {
        2020: [10, 10],
        2021: [10, 10],
        2022: [10, 10],
        2023: [10, 10],
        2024: [10, 10],
        2025: [10, 10],
      },
      2,
    );
    const rows = [makeYear(2025, { quarters: 2, marketCapAdjusted: 400 })];
    const result = computeTrailingPERatios(rows, source, 6);
    expect(result.get(2025)!.pe).toBe(20);
  });

  it("returns null when the anchored window lacks enough filings", () => {
    const source = makeSource({
      2023: [25, 25, 25, 25],
      2024: [25, 25, 25, 25],
    });
    const rows = [
      makeYear(2024, { marketCapAdjusted: 500 }),
      makeYear(2023, { marketCapAdjusted: 400 }),
    ];
    const result = computeTrailingPERatios(rows, source, 3);
    // Only 2 years of filings exist — a 3-year window is not computable
    // for either row. No silently-shrunk averages.
    expect(result.get(2024)!.pe).toBeNull();
    expect(result.get(2023)!.pe).toBeNull();
  });

  it("returns null ratios when market cap is missing", () => {
    const source = makeSource({ 2024: [25, 25, 25, 25] });
    const rows = [makeYear(2024, { marketCapAdjusted: null, marketCap: null })];
    const result = computeTrailingPERatios(rows, source, 1);
    expect(result.get(2024)).toEqual({ pe: null, pfcf: null });
  });

  it("returns null ratios when the quote payload is unavailable", () => {
    const rows = [makeYear(2024, { marketCapAdjusted: 500 })];
    const result = computeTrailingPERatios(rows, null, 3);
    expect(result.get(2024)).toEqual({ pe: null, pfcf: null });
  });

  it("computes negative PE when the window average is negative", () => {
    const source = makeSource({ 2024: [-25, -25, -25, -25] });
    const rows = [makeYear(2024, { marketCapAdjusted: 1000 })];
    const result = computeTrailingPERatios(rows, source, 1);
    expect(result.get(2024)!.pe).toBe(-10);
  });

  it("returns null when the window average is exactly zero", () => {
    const source = makeSource({ 2024: [50, -50, 25, -25] });
    const rows = [makeYear(2024, { marketCapAdjusted: 1000 })];
    const result = computeTrailingPERatios(rows, source, 1);
    expect(result.get(2024)!.pe).toBeNull();
  });

  it("computes P/FCL from the cash-flow details", () => {
    // makeSource sets each FCF filing to half the earnings filing:
    // avg FCF = 50 → PFCF = 500/50 = 10.
    const source = makeSource({
      2022: [25, 25, 25, 25],
      2023: [25, 25, 25, 25],
      2024: [25, 25, 25, 25],
    });
    const rows = [makeYear(2024, { marketCapAdjusted: 500 })];
    const result = computeTrailingPERatios(rows, source, 3);
    expect(result.get(2024)!.pfcf).toBe(10.0);
  });

  it("falls back to nominal market cap when the adjusted value is missing", () => {
    const source = makeSource({ 2024: [25, 25, 25, 25] });
    const rows = [makeYear(2024, { marketCapAdjusted: null, marketCap: 500 })];
    const result = computeTrailingPERatios(rows, source, 1);
    expect(result.get(2024)!.pe).toBe(5.0);
  });
});

describe("augmentWithPERatios", () => {
  const source = makeSource({
    2020: [25, 25, 25, 25],
    2021: [25, 25, 25, 25],
    2022: [25, 25, 25, 25],
    2023: [25, 25, 25, 25],
    2024: [25, 25, 25, 25],
  });

  it("always returns data sorted by year descending (latest first)", () => {
    const ascendingData = [
      makeYear(2020, { marketCapAdjusted: 100 }),
      makeYear(2021, { marketCapAdjusted: 200 }),
      makeYear(2022, { marketCapAdjusted: 300 }),
      makeYear(2023, { marketCapAdjusted: 400 }),
      makeYear(2024, { marketCapAdjusted: 500 }),
    ];
    const result = augmentWithPERatios(ascendingData, 5, source);
    const years = result.map((row) => row.year);
    expect(years).toEqual([2024, 2023, 2022, 2021, 2020]);
  });

  it("attaches pe and pfcf for the requested window", () => {
    const data = [
      makeYear(2024, { marketCapAdjusted: 500 }),
      makeYear(2023, { marketCapAdjusted: 400 }),
      makeYear(2022, { marketCapAdjusted: 300 }),
    ];
    const result = augmentWithPERatios(data, 3, source);
    expect(result[0].pe).toBe(5.0);
    expect(result[0].pfcf).toBe(10.0);
  });
});

describe("formatNumber formatting", () => {
  it("uses en-dash (U+2013) for negative numbers", () => {
    const formatted = formatNumber(-1234.56, 2, "pt");
    expect(formatted).toContain("–");
    expect(formatted).not.toContain("-");
  });

  it("does not alter positive numbers", () => {
    const formatted = formatNumber(1234.56, 2, "pt");
    expect(formatted).not.toContain("–");
    expect(formatted).not.toContain("-");
  });
});
