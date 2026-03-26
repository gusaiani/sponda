import { describe, it, expect } from "vitest";
import { computeShillerPERatios } from "./FundamentalsTab";
import { br } from "../utils/format";
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
  it("returns null for all ratios when marketCap is null", () => {
    const data = [makeYear(2024, { marketCap: null, netIncomeAdjusted: 100, fcfAdjusted: 100 })];
    const result = computeShillerPERatios(data);
    expect(result.get(2024)).toEqual({ pe10: null, pe5: null, pfcl10: null, pfcl5: null });
  });

  it("returns null when netIncomeAdjusted and fcfAdjusted are null for all years", () => {
    const data = [
      makeYear(2024, { marketCap: 1000, netIncomeAdjusted: null, fcfAdjusted: null }),
    ];
    const result = computeShillerPERatios(data);
    expect(result.get(2024)).toEqual({ pe10: null, pe5: null, pfcl10: null, pfcl5: null });
  });

  it("computes negative P/E when average earnings are negative", () => {
    const data = [
      makeYear(2024, { marketCap: 1000, netIncomeAdjusted: -100 }),
      makeYear(2023, { marketCap: 1000, netIncomeAdjusted: -200 }),
    ];
    const result = computeShillerPERatios(data);
    // avg earnings = (-100 + -200) / 2 = -150, PE5 = 1000 / -150 = -6.7
    expect(result.get(2024)!.pe5).toBe(-6.7);
    expect(result.get(2024)!.pe10).toBe(-6.7);
  });

  it("computes PE5 using up to 5 years of data", () => {
    const data = [
      makeYear(2024, { marketCap: 500, netIncomeAdjusted: 100 }),
      makeYear(2023, { marketCap: 400, netIncomeAdjusted: 100 }),
      makeYear(2022, { marketCap: 300, netIncomeAdjusted: 100 }),
      makeYear(2021, { marketCap: 200, netIncomeAdjusted: 100 }),
      makeYear(2020, { marketCap: 100, netIncomeAdjusted: 100 }),
    ];
    const result = computeShillerPERatios(data);
    // avg earnings = 100, PE5(2024) = 500 / 100 = 5.0
    expect(result.get(2024)!.pe5).toBe(5.0);
  });

  it("computes PE10 using up to 10 years of data", () => {
    const years = Array.from({ length: 10 }, (_, index) =>
      makeYear(2024 - index, {
        marketCap: 1000,
        netIncomeAdjusted: 100,
      }),
    );
    const result = computeShillerPERatios(years);
    // avg = 100, PE10(2024) = 1000 / 100 = 10.0
    expect(result.get(2024)!.pe10).toBe(10.0);
  });

  it("PE5 only considers the last 5 years even when more data exists", () => {
    const years = [
      makeYear(2024, { marketCap: 1000, netIncomeAdjusted: 200 }),
      makeYear(2023, { marketCap: 900, netIncomeAdjusted: 200 }),
      makeYear(2022, { marketCap: 800, netIncomeAdjusted: 200 }),
      makeYear(2021, { marketCap: 700, netIncomeAdjusted: 200 }),
      makeYear(2020, { marketCap: 600, netIncomeAdjusted: 200 }),
      // These should NOT be included in PE5 for 2024
      makeYear(2019, { marketCap: 500, netIncomeAdjusted: 10 }),
      makeYear(2018, { marketCap: 400, netIncomeAdjusted: 10 }),
    ];
    const result = computeShillerPERatios(years);
    // PE5(2024) = 1000 / 200 = 5.0 (only 2020-2024)
    expect(result.get(2024)!.pe5).toBe(5.0);
  });

  it("uses available years when fewer than window size exist", () => {
    const data = [
      makeYear(2024, { marketCap: 300, netIncomeAdjusted: 100 }),
      makeYear(2023, { marketCap: 200, netIncomeAdjusted: 100 }),
    ];
    const result = computeShillerPERatios(data);
    // Only 2 years available, avg = 100
    // PE5(2024) = 300 / 100 = 3.0
    // PE10(2024) = 300 / 100 = 3.0
    expect(result.get(2024)!.pe5).toBe(3.0);
    expect(result.get(2024)!.pe10).toBe(3.0);
  });

  it("rounds to one decimal place", () => {
    const data = [
      makeYear(2024, { marketCap: 1000, netIncomeAdjusted: 300 }),
    ];
    const result = computeShillerPERatios(data);
    // 1000 / 300 = 3.333... → 3.3
    expect(result.get(2024)!.pe5).toBe(3.3);
  });

  it("handles descending-order input correctly", () => {
    // Data sorted descending (as from backend)
    const data = [
      makeYear(2024, { marketCap: 500, netIncomeAdjusted: 100 }),
      makeYear(2023, { marketCap: 400, netIncomeAdjusted: 100 }),
      makeYear(2022, { marketCap: 300, netIncomeAdjusted: 100 }),
    ];
    const result = computeShillerPERatios(data);
    expect(result.get(2024)!.pe5).toBe(5.0);
    expect(result.get(2022)!.pe5).toBe(3.0);
  });

  it("computes different PE5 and PE10 when earnings vary across windows", () => {
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
    const result = computeShillerPERatios(years);
    // PE5(2024): avg of 2020-2024 = 200, ratio = 1000/200 = 5.0
    expect(result.get(2024)!.pe5).toBe(5.0);
    // PE10(2024): avg of 2015-2024 = (5*200 + 5*50)/10 = 125, ratio = 1000/125 = 8.0
    expect(result.get(2024)!.pe10).toBe(8.0);
  });

  it("skips null netIncomeAdjusted years but still computes average from available data", () => {
    const data = [
      makeYear(2024, { marketCap: 600, netIncomeAdjusted: 200 }),
      makeYear(2023, { marketCap: 500, netIncomeAdjusted: null }),
      makeYear(2022, { marketCap: 400, netIncomeAdjusted: 100 }),
    ];
    const result = computeShillerPERatios(data);
    // avg of non-null: (200 + 100) / 2 = 150
    // PE5(2024) = 600 / 150 = 4.0
    expect(result.get(2024)!.pe5).toBe(4.0);
  });

  it("computes P/FCL5 using up to 5 years of fcfAdjusted data", () => {
    const data = [
      makeYear(2024, { marketCap: 500, fcfAdjusted: 50 }),
      makeYear(2023, { marketCap: 400, fcfAdjusted: 50 }),
      makeYear(2022, { marketCap: 300, fcfAdjusted: 50 }),
      makeYear(2021, { marketCap: 200, fcfAdjusted: 50 }),
      makeYear(2020, { marketCap: 100, fcfAdjusted: 50 }),
    ];
    const result = computeShillerPERatios(data);
    // avg FCF = 50, P/FCL5(2024) = 500 / 50 = 10.0
    expect(result.get(2024)!.pfcl5).toBe(10.0);
  });

  it("computes P/FCL10 using up to 10 years of fcfAdjusted data", () => {
    const years = Array.from({ length: 10 }, (_, index) =>
      makeYear(2024 - index, {
        marketCap: 1000,
        fcfAdjusted: 100,
      }),
    );
    const result = computeShillerPERatios(years);
    // avg = 100, P/FCL10(2024) = 1000 / 100 = 10.0
    expect(result.get(2024)!.pfcl10).toBe(10.0);
  });

  it("computes negative P/FCL when average FCF is negative", () => {
    const data = [
      makeYear(2024, { marketCap: 1000, fcfAdjusted: -100 }),
      makeYear(2023, { marketCap: 1000, fcfAdjusted: -200 }),
    ];
    const result = computeShillerPERatios(data);
    // avg FCF = (-100 + -200) / 2 = -150, P/FCL5 = 1000 / -150 = -6.7
    expect(result.get(2024)!.pfcl5).toBe(-6.7);
    expect(result.get(2024)!.pfcl10).toBe(-6.7);
  });

  it("computes different P/FCL5 and P/FCL10 when FCF varies across windows", () => {
    const years = [
      makeYear(2024, { marketCap: 1000, fcfAdjusted: 200 }),
      makeYear(2023, { marketCap: 900, fcfAdjusted: 200 }),
      makeYear(2022, { marketCap: 800, fcfAdjusted: 200 }),
      makeYear(2021, { marketCap: 700, fcfAdjusted: 200 }),
      makeYear(2020, { marketCap: 600, fcfAdjusted: 200 }),
      makeYear(2019, { marketCap: 500, fcfAdjusted: 50 }),
      makeYear(2018, { marketCap: 400, fcfAdjusted: 50 }),
      makeYear(2017, { marketCap: 300, fcfAdjusted: 50 }),
      makeYear(2016, { marketCap: 200, fcfAdjusted: 50 }),
      makeYear(2015, { marketCap: 100, fcfAdjusted: 50 }),
    ];
    const result = computeShillerPERatios(years);
    // P/FCL5(2024): avg of 2020-2024 = 200, ratio = 1000/200 = 5.0
    expect(result.get(2024)!.pfcl5).toBe(5.0);
    // P/FCL10(2024): avg of 2015-2024 = (5*200 + 5*50)/10 = 125, ratio = 1000/125 = 8.0
    expect(result.get(2024)!.pfcl10).toBe(8.0);
  });

  it("returns null when average is exactly zero (division by zero)", () => {
    const data = [
      makeYear(2024, { marketCap: 1000, netIncomeAdjusted: 100, fcfAdjusted: 50 }),
      makeYear(2023, { marketCap: 1000, netIncomeAdjusted: -100, fcfAdjusted: -50 }),
    ];
    const result = computeShillerPERatios(data);
    // avg earnings = 0, should be null (division by zero)
    expect(result.get(2024)!.pe5).toBeNull();
    expect(result.get(2024)!.pfcl5).toBeNull();
  });
});

describe("br() formatting", () => {
  it("uses n-dash (U+2013) for negative numbers", () => {
    const formatted = br(-1234.56, 2);
    // Should contain n-dash, not hyphen-minus
    expect(formatted).toContain("\u2013");
    expect(formatted).not.toContain("-");
  });

  it("does not alter positive numbers", () => {
    const formatted = br(1234.56, 2);
    expect(formatted).not.toContain("\u2013");
    expect(formatted).not.toContain("-");
  });
});
