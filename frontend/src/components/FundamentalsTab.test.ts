import { describe, it, expect } from "vitest";
import { computeShillerPERatios, augmentWithPERatios } from "./FundamentalsTab";
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

describe("computeShillerPERatios", () => {
  it("returns null for both ratios when marketCap is null", () => {
    const data = [makeYear(2024, { marketCap: null, netIncomeAdjusted: 100, fcfAdjusted: 100 })];
    const result = computeShillerPERatios(data, 5);
    expect(result.get(2024)).toEqual({ pe: null, pfcf: null });
  });

  it("returns null when netIncomeAdjusted and fcfAdjusted are null for all years", () => {
    const data = [
      makeYear(2024, { marketCap: 1000, netIncomeAdjusted: null, fcfAdjusted: null }),
    ];
    const result = computeShillerPERatios(data, 5);
    expect(result.get(2024)).toEqual({ pe: null, pfcf: null });
  });

  it("computes negative P/E when average earnings are negative", () => {
    const data = [
      makeYear(2024, { marketCap: 1000, netIncomeAdjusted: -100 }),
      makeYear(2023, { marketCap: 1000, netIncomeAdjusted: -200 }),
    ];
    const result = computeShillerPERatios(data, 5);
    // avg earnings = (-100 + -200) / 2 = -150, PE = 1000 / -150 = -6.7
    expect(result.get(2024)!.pe).toBe(-6.7);
  });

  it("computes PE using up to N years of data", () => {
    const data = [
      makeYear(2024, { marketCap: 500, netIncomeAdjusted: 100 }),
      makeYear(2023, { marketCap: 400, netIncomeAdjusted: 100 }),
      makeYear(2022, { marketCap: 300, netIncomeAdjusted: 100 }),
      makeYear(2021, { marketCap: 200, netIncomeAdjusted: 100 }),
      makeYear(2020, { marketCap: 100, netIncomeAdjusted: 100 }),
    ];
    const result = computeShillerPERatios(data, 5);
    expect(result.get(2024)!.pe).toBe(5.0);
  });

  it("PE5 only considers the last 5 years even when more data exists", () => {
    const years = [
      makeYear(2024, { marketCap: 1000, netIncomeAdjusted: 200 }),
      makeYear(2023, { marketCap: 900, netIncomeAdjusted: 200 }),
      makeYear(2022, { marketCap: 800, netIncomeAdjusted: 200 }),
      makeYear(2021, { marketCap: 700, netIncomeAdjusted: 200 }),
      makeYear(2020, { marketCap: 600, netIncomeAdjusted: 200 }),
      makeYear(2019, { marketCap: 500, netIncomeAdjusted: 10 }),
      makeYear(2018, { marketCap: 400, netIncomeAdjusted: 10 }),
    ];
    const result = computeShillerPERatios(years, 5);
    // PE5(2024) = 1000 / 200 = 5.0 (only 2020-2024)
    expect(result.get(2024)!.pe).toBe(5.0);
  });

  it("uses available years when fewer than window size exist", () => {
    const data = [
      makeYear(2024, { marketCap: 300, netIncomeAdjusted: 100 }),
      makeYear(2023, { marketCap: 200, netIncomeAdjusted: 100 }),
    ];
    const result = computeShillerPERatios(data, 5);
    // Only 2 years available, avg = 100, PE = 300/100 = 3.0
    expect(result.get(2024)!.pe).toBe(3.0);
  });

  it("rounds to one decimal place", () => {
    const data = [
      makeYear(2024, { marketCap: 1000, netIncomeAdjusted: 300 }),
    ];
    const result = computeShillerPERatios(data, 5);
    // 1000 / 300 = 3.333... → 3.3
    expect(result.get(2024)!.pe).toBe(3.3);
  });

  it("handles descending-order input correctly", () => {
    const data = [
      makeYear(2024, { marketCap: 500, netIncomeAdjusted: 100 }),
      makeYear(2023, { marketCap: 400, netIncomeAdjusted: 100 }),
      makeYear(2022, { marketCap: 300, netIncomeAdjusted: 100 }),
    ];
    const result = computeShillerPERatios(data, 5);
    expect(result.get(2024)!.pe).toBe(5.0);
    expect(result.get(2022)!.pe).toBe(3.0);
  });

  it("PE5 and PE10 differ when earnings vary across windows", () => {
    const years = [
      makeYear(2024, { marketCap: 1000, netIncomeAdjusted: 200 }),
      makeYear(2023, { marketCap: 900, netIncomeAdjusted: 200 }),
      makeYear(2022, { marketCap: 800, netIncomeAdjusted: 200 }),
      makeYear(2021, { marketCap: 700, netIncomeAdjusted: 200 }),
      makeYear(2020, { marketCap: 600, netIncomeAdjusted: 200 }),
      makeYear(2019, { marketCap: 500, netIncomeAdjusted: 50 }),
      makeYear(2018, { marketCap: 400, netIncomeAdjusted: 50 }),
      makeYear(2017, { marketCap: 300, netIncomeAdjusted: 50 }),
      makeYear(2016, { marketCap: 200, netIncomeAdjusted: 50 }),
      makeYear(2015, { marketCap: 100, netIncomeAdjusted: 50 }),
    ];
    expect(computeShillerPERatios(years, 5).get(2024)!.pe).toBe(5.0);
    expect(computeShillerPERatios(years, 10).get(2024)!.pe).toBe(8.0);
  });

  it("skips null netIncomeAdjusted years but still computes average from available data", () => {
    const data = [
      makeYear(2024, { marketCap: 600, netIncomeAdjusted: 200 }),
      makeYear(2023, { marketCap: 500, netIncomeAdjusted: null }),
      makeYear(2022, { marketCap: 400, netIncomeAdjusted: 100 }),
    ];
    const result = computeShillerPERatios(data, 5);
    // avg of non-null: (200 + 100) / 2 = 150, PE = 600/150 = 4.0
    expect(result.get(2024)!.pe).toBe(4.0);
  });

  it("computes P/FCF using up to N years of fcfAdjusted data", () => {
    const data = [
      makeYear(2024, { marketCap: 500, fcfAdjusted: 50 }),
      makeYear(2023, { marketCap: 400, fcfAdjusted: 50 }),
      makeYear(2022, { marketCap: 300, fcfAdjusted: 50 }),
      makeYear(2021, { marketCap: 200, fcfAdjusted: 50 }),
      makeYear(2020, { marketCap: 100, fcfAdjusted: 50 }),
    ];
    const result = computeShillerPERatios(data, 5);
    // avg FCF = 50, PFCF = 500/50 = 10.0
    expect(result.get(2024)!.pfcf).toBe(10.0);
  });

  it("computes negative P/FCF when average FCF is negative", () => {
    const data = [
      makeYear(2024, { marketCap: 1000, fcfAdjusted: -100 }),
      makeYear(2023, { marketCap: 1000, fcfAdjusted: -200 }),
    ];
    const result = computeShillerPERatios(data, 5);
    // avg = -150, PFCF = 1000/-150 = -6.7
    expect(result.get(2024)!.pfcf).toBe(-6.7);
  });

  it("returns null when average is exactly zero (division by zero)", () => {
    const data = [
      makeYear(2024, { marketCap: 1000, netIncomeAdjusted: 100, fcfAdjusted: 50 }),
      makeYear(2023, { marketCap: 1000, netIncomeAdjusted: -100, fcfAdjusted: -50 }),
    ];
    const result = computeShillerPERatios(data, 5);
    expect(result.get(2024)!.pe).toBeNull();
    expect(result.get(2024)!.pfcf).toBeNull();
  });
});

describe("augmentWithPERatios", () => {
  it("always returns data sorted by year descending (latest first)", () => {
    const ascendingData = [
      makeYear(2020, { marketCap: 100, netIncomeAdjusted: 50 }),
      makeYear(2021, { marketCap: 200, netIncomeAdjusted: 60 }),
      makeYear(2022, { marketCap: 300, netIncomeAdjusted: 70 }),
      makeYear(2023, { marketCap: 400, netIncomeAdjusted: 80 }),
      makeYear(2024, { marketCap: 500, netIncomeAdjusted: 90 }),
    ];
    const result = augmentWithPERatios(ascendingData, 5);
    const years = result.map((row) => row.year);
    expect(years).toEqual([2024, 2023, 2022, 2021, 2020]);
  });

  it("preserves descending order when data is already sorted correctly", () => {
    const descendingData = [
      makeYear(2024, { marketCap: 500 }),
      makeYear(2023, { marketCap: 400 }),
      makeYear(2022, { marketCap: 300 }),
    ];
    const result = augmentWithPERatios(descendingData, 5);
    const years = result.map((row) => row.year);
    expect(years).toEqual([2024, 2023, 2022]);
  });

  it("attaches pe and pfcf for the requested window", () => {
    const data = [
      makeYear(2024, { marketCap: 500, netIncomeAdjusted: 100, fcfAdjusted: 50 }),
      makeYear(2023, { marketCap: 400, netIncomeAdjusted: 100, fcfAdjusted: 50 }),
      makeYear(2022, { marketCap: 300, netIncomeAdjusted: 100, fcfAdjusted: 50 }),
    ];
    const result = augmentWithPERatios(data, 3);
    expect(result[0].pe).toBe(5.0);
    expect(result[0].pfcf).toBe(10.0);
  });
});

describe("formatNumber formatting", () => {
  it("uses en-dash (U+2013) for negative numbers", () => {
    const formatted = formatNumber(-1234.56, 2, "pt");
    expect(formatted).toContain("\u2013");
    expect(formatted).not.toContain("-");
  });

  it("does not alter positive numbers", () => {
    const formatted = formatNumber(1234.56, 2, "pt");
    expect(formatted).not.toContain("\u2013");
    expect(formatted).not.toContain("-");
  });
});
