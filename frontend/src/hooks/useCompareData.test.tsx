// @vitest-environment jsdom
import { describe, it, expect, vi } from "vitest";
import React from "react";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useCompareData } from "./useCompareData";
import type { QuoteResult } from "./usePE10";

/**
 * Compare-tab regression: P/L and P/FCL must be the same window-aware
 * trailing-periods numbers the Indicadores tab shows (deriveForYears),
 * not a calendar-year average that counts a partial current year as a
 * full one.
 *
 * Scenario: current year has only Q1 filed ($10); the three prior years
 * earn $40 each. A 3-year trailing window averages $40/year → PE 10.
 * The old calendar-year math averaged (10+40+40)/3 ≈ 30 → PE 13.3.
 */

function makeQuote(): QuoteResult {
  const yearLayouts = [
    { year: 2026, quarterValues: [10] },
    { year: 2025, quarterValues: [10, 10, 10, 10] },
    { year: 2024, quarterValues: [10, 10, 10, 10] },
    { year: 2023, quarterValues: [10, 10, 10, 10] },
  ];
  const pe10CalculationDetails = yearLayouts.map((y) => ({
    year: y.year,
    nominalNetIncome: y.quarterValues.reduce((s, v) => s + v, 0),
    ipcaFactor: 1,
    adjustedNetIncome: y.quarterValues.reduce((s, v) => s + v, 0),
    quarters: y.quarterValues.length,
    quarterlyDetail: y.quarterValues.map((v, i) => ({
      end_date: `${y.year}-${String((i + 1) * 3).padStart(2, "0")}-30`,
      net_income: v,
    })),
  }));
  const pfcf10CalculationDetails = yearLayouts.map((y) => ({
    year: y.year,
    nominalFCF: y.quarterValues.reduce((s, v) => s + v, 0),
    ipcaFactor: 1,
    adjustedFCF: y.quarterValues.reduce((s, v) => s + v, 0),
    quarters: y.quarterValues.length,
    quarterlyDetail: y.quarterValues.map((v, i) => ({
      end_date: `${y.year}-${String((i + 1) * 3).padStart(2, "0")}-30`,
      operating_cash_flow: v,
      investment_cash_flow: 0,
      fcf: v,
    })),
  }));
  return {
    ticker: "TEST4",
    name: "Test Co",
    logo: "",
    currentPrice: 1,
    marketCap: 400,
    maxYearsAvailable: 3,
    pe10: null,
    avgAdjustedNetIncome: null,
    pe10YearsOfData: 0,
    pe10Label: "PE0",
    pe10Error: null,
    pe10AnnualData: false,
    pe10PeriodsPerYear: 4,
    pe10CalculationDetails,
    pfcf10: null,
    avgAdjustedFCF: null,
    pfcf10YearsOfData: 0,
    pfcf10Label: "PFCF0",
    pfcf10Error: null,
    pfcf10AnnualData: false,
    pfcf10PeriodsPerYear: 4,
    pfcf10CalculationDetails,
    debtToEquity: null,
    debtExLeaseToEquity: null,
    liabilitiesToEquity: null,
    currentRatio: null,
    leverageError: null,
    leverageDate: null,
    totalDebt: null,
    totalLease: null,
    totalLiabilities: null,
    stockholdersEquity: null,
    debtToAvgEarnings: null,
    debtToAvgFCF: null,
    peg: null,
    earningsCAGR: null,
    pegError: null,
    earningsCAGRMethod: null,
    earningsCAGRExcludedYears: [],
    pfcfPeg: null,
    fcfCAGR: null,
    pfcfPegError: null,
    fcfCAGRMethod: null,
    fcfCAGRExcludedYears: [],
    roe: null,
    priceToBook: null,
  };
}

function makeFundamentalsYear(year: number, netIncome: number, quarters: number) {
  return {
    year,
    quarters,
    revenue: null, revenueAdjusted: null,
    netIncome, netIncomeAdjusted: netIncome,
    fcf: netIncome, fcfAdjusted: netIncome,
    operatingCashFlow: null, operatingCashFlowAdjusted: null,
    debtExLease: null, debtExLeaseAdjusted: null,
    totalLiabilities: null, totalLiabilitiesAdjusted: null,
    stockholdersEquity: null, stockholdersEquityAdjusted: null,
    debtToEquity: null, liabilitiesToEquity: null, currentRatio: null,
    marketCap: 400, marketCapAdjusted: 400,
    dividendsPaid: null, dividendsAdjusted: null,
  };
}

vi.mock("./useQuotesBatch", () => ({
  useQuotesBatch: () => ({
    data: { results: { TEST4: { quote: makeQuote() } } },
    isLoading: false,
    error: null,
  }),
}));

vi.mock("./useFundamentals", () => ({
  fetchFundamentals: vi.fn(async () => ({
    years: [
      makeFundamentalsYear(2026, 10, 1),
      makeFundamentalsYear(2025, 40, 4),
      makeFundamentalsYear(2024, 40, 4),
      makeFundamentalsYear(2023, 40, 4),
    ],
  })),
}));

function wrapper({ children }: { children: React.ReactNode }) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return React.createElement(QueryClientProvider, { client: queryClient }, children);
}

describe("useCompareData ratios", () => {
  it("uses the window-aware trailing-periods P/L and P/FCL (same as Indicadores)", async () => {
    const { result } = renderHook(() => useCompareData(["TEST4"], 3), { wrapper });

    await waitFor(() => expect(result.current[0].isLoading).toBe(false));

    const entry = result.current[0];
    // Trailing 12 quarters ($120) ÷ 3 years = $40 avg → PE = 400/40 = 10.
    // The old calendar-year math produced 13.3 here.
    expect(entry.pe).toBe(10);
    expect(entry.pfcf).toBe(10);
    // They must equal the derived quote values used by the Indicadores tab.
    expect(entry.pe).toBe(entry.data?.pe10);
    expect(entry.pfcf).toBe(entry.data?.pfcf10);
  });

  it("still exposes the most recent fundamentals year for the other columns", async () => {
    const { result } = renderHook(() => useCompareData(["TEST4"], 3), { wrapper });

    await waitFor(() => expect(result.current[0].isLoading).toBe(false));

    expect(result.current[0].recent?.year).toBe(2026);
  });
});
