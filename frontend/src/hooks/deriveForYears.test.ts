import { describe, it, expect } from "vitest";
import { deriveForYears } from "./deriveForYears";
import type { QuoteResult } from "./usePE10";

/** Helper: build a minimal QuoteResult with N years of earnings and FCF data */
function makeFullData(opts: {
  years: number;
  marketCap?: number;
  totalDebt?: number | null;
  /** Yearly adjusted earnings (index 0 = most recent year) */
  earnings?: number[];
  /** Yearly adjusted FCF (index 0 = most recent year) */
  fcf?: number[];
}): QuoteResult {
  const { years, marketCap = 1_000_000, totalDebt = null } = opts;
  const earnings = opts.earnings ?? Array.from({ length: years }, () => 100_000);
  const fcf = opts.fcf ?? Array.from({ length: years }, () => 80_000);
  const currentYear = 2025;

  return {
    ticker: "TEST4",
    name: "Test Co",
    logo: "",
    currentPrice: 10,
    marketCap,
    maxYearsAvailable: years,
    // PE10 (full data)
    pe10: null,
    avgAdjustedNetIncome: null,
    pe10YearsOfData: years,
    pe10Label: `PE${years}`,
    pe10Error: null,
    pe10AnnualData: false,
    pe10CalculationDetails: earnings.map((v, i) => ({
      year: currentYear - i,
      nominalNetIncome: v,
      ipcaFactor: 1,
      adjustedNetIncome: v,
      quarters: 4,
      quarterlyDetail: [],
    })),
    // PFCF10 (full data)
    pfcf10: null,
    avgAdjustedFCF: null,
    pfcf10YearsOfData: years,
    pfcf10Label: `PFCF${years}`,
    pfcf10Error: null,
    pfcf10AnnualData: false,
    pfcf10CalculationDetails: fcf.map((v, i) => ({
      year: currentYear - i,
      nominalFCF: v,
      ipcaFactor: 1,
      adjustedFCF: v,
      quarters: 4,
      quarterlyDetail: [],
    })),
    // Leverage (pass-through, not derived)
    debtToEquity: null,
    debtExLeaseToEquity: null,
    liabilitiesToEquity: null,
    leverageError: null,
    leverageDate: null,
    totalDebt,
    totalLease: null,
    totalLiabilities: null,
    stockholdersEquity: null,
    // Debt coverage (will be derived)
    debtToAvgEarnings: null,
    debtToAvgFCF: null,
    // PEG (will be derived)
    peg: null,
    earningsCAGR: null,
    pegError: null,
    earningsCAGRMethod: null,
    earningsCAGRExcludedYears: [],
    // PFCLG (will be derived)
    pfcfPeg: null,
    fcfCAGR: null,
    pfcfPegError: null,
    fcfCAGRMethod: null,
    fcfCAGRExcludedYears: [],
    // Profitability (will be derived)
    roe: null,
    priceToBook: null,
  };
}

describe("deriveForYears", () => {
  describe("slicing", () => {
    it("uses only the requested number of years", () => {
      const full = makeFullData({ years: 10 });
      const derived = deriveForYears(full, 3);

      expect(derived.pe10YearsOfData).toBe(3);
      expect(derived.pfcf10YearsOfData).toBe(3);
      expect(derived.pe10CalculationDetails).toHaveLength(3);
      expect(derived.pfcf10CalculationDetails).toHaveLength(3);
      expect(derived.pe10Label).toBe("PE3");
      expect(derived.pfcf10Label).toBe("PFCF3");
    });

    it("caps at available data when requesting more years than exist", () => {
      const full = makeFullData({ years: 5 });
      const derived = deriveForYears(full, 20);

      expect(derived.pe10YearsOfData).toBe(5);
      expect(derived.pfcf10YearsOfData).toBe(5);
    });

    it("handles 1 year", () => {
      const full = makeFullData({ years: 10 });
      const derived = deriveForYears(full, 1);

      expect(derived.pe10YearsOfData).toBe(1);
      expect(derived.pe10Label).toBe("PE1");
    });
  });

  describe("PE10 / PFCF10 computation", () => {
    it("computes PE10 as marketCap / average adjusted earnings", () => {
      const full = makeFullData({
        years: 4,
        marketCap: 400_000,
        earnings: [100_000, 100_000, 100_000, 100_000],
      });
      const derived = deriveForYears(full, 4);

      // avg = 100_000, PE = 400_000 / 100_000 = 4.0
      expect(derived.pe10).toBe(4.0);
      expect(derived.avgAdjustedNetIncome).toBe(100_000);
    });

    it("slicing fewer years changes the average", () => {
      const full = makeFullData({
        years: 4,
        marketCap: 400_000,
        // Most recent 2 years earn more
        earnings: [200_000, 200_000, 50_000, 50_000],
      });
      const derived2 = deriveForYears(full, 2);
      const derived4 = deriveForYears(full, 4);

      // 2-year avg = 200_000, PE = 2.0
      expect(derived2.pe10).toBe(2.0);
      // 4-year avg = 125_000, PE = 3.2
      expect(derived4.pe10).toBe(3.2);
    });

    it("returns null PE10 with error when average earnings <= 0", () => {
      const full = makeFullData({
        years: 3,
        marketCap: 100_000,
        earnings: [-50_000, -50_000, -50_000],
      });
      const derived = deriveForYears(full, 3);

      expect(derived.pe10).toBeNull();
      expect(derived.pe10Error).toContain("negativo");
    });

    it("computes PFCF10 as marketCap / average adjusted FCF", () => {
      const full = makeFullData({
        years: 5,
        marketCap: 500_000,
        fcf: [100_000, 100_000, 100_000, 100_000, 100_000],
      });
      const derived = deriveForYears(full, 5);

      expect(derived.pfcf10).toBe(5.0);
    });
  });

  describe("debt coverage", () => {
    it("computes debt / avg earnings and debt / avg FCF", () => {
      const full = makeFullData({
        years: 5,
        totalDebt: 500_000,
        earnings: [100_000, 100_000, 100_000, 100_000, 100_000],
        fcf: [50_000, 50_000, 50_000, 50_000, 50_000],
      });
      const derived = deriveForYears(full, 5);

      // 500_000 / 100_000 = 5.0
      expect(derived.debtToAvgEarnings).toBe(5.0);
      // 500_000 / 50_000 = 10.0
      expect(derived.debtToAvgFCF).toBe(10.0);
    });

    it("returns null when totalDebt is null", () => {
      const full = makeFullData({ years: 5, totalDebt: null });
      const derived = deriveForYears(full, 5);

      expect(derived.debtToAvgEarnings).toBeNull();
      expect(derived.debtToAvgFCF).toBeNull();
    });
  });

  describe("CAGR — endpoint method", () => {
    it("computes endpoint CAGR when both endpoints are positive", () => {
      // Earnings double over 4 years: 100 → 200
      // CAGR = (200/100)^(1/4) - 1 ≈ 18.92%
      const full = makeFullData({
        years: 5,
        marketCap: 1_000_000,
        earnings: [200_000, 175_000, 150_000, 125_000, 100_000],
      });
      const derived = deriveForYears(full, 5);

      expect(derived.earningsCAGRMethod).toBe("endpoint");
      expect(derived.earningsCAGR).toBeCloseTo(18.92, 1);
    });
  });

  describe("CAGR — regression fallback", () => {
    it("uses regression when an endpoint is negative", () => {
      const full = makeFullData({
        years: 5,
        marketCap: 1_000_000,
        // Most recent is positive, oldest is negative → endpoint fails
        earnings: [100_000, 80_000, 60_000, 40_000, -10_000],
      });
      const derived = deriveForYears(full, 5);

      expect(derived.earningsCAGRMethod).toBe("regression");
      expect(derived.earningsCAGRExcludedYears.length).toBeGreaterThan(0);
      expect(derived.earningsCAGR).not.toBeNull();
    });

    it("returns null CAGR when fewer than 2 positive years", () => {
      const full = makeFullData({
        years: 3,
        marketCap: 1_000_000,
        earnings: [50_000, -100_000, -100_000],
      });
      const derived = deriveForYears(full, 3);

      expect(derived.earningsCAGR).toBeNull();
    });
  });

  describe("PEG / PFCLG", () => {
    it("computes PEG as PE / CAGR when both are positive", () => {
      const full = makeFullData({
        years: 5,
        marketCap: 1_000_000,
        earnings: [200_000, 175_000, 150_000, 125_000, 100_000],
      });
      const derived = deriveForYears(full, 5);

      expect(derived.pe10).not.toBeNull();
      expect(derived.earningsCAGR).not.toBeNull();
      expect(derived.peg).not.toBeNull();
      // PEG = PE / CAGR
      expect(derived.peg).toBeCloseTo(derived.pe10! / derived.earningsCAGR!, 1);
    });

    it("returns PEG error when PE is null", () => {
      const full = makeFullData({
        years: 3,
        marketCap: 1_000_000,
        earnings: [-50_000, -50_000, -50_000],
      });
      const derived = deriveForYears(full, 3);

      expect(derived.peg).toBeNull();
      expect(derived.pegError).toBeTruthy();
    });

    it("returns PEG error when CAGR is negative", () => {
      // Declining earnings
      const full = makeFullData({
        years: 5,
        marketCap: 1_000_000,
        earnings: [50_000, 75_000, 100_000, 125_000, 200_000],
      });
      const derived = deriveForYears(full, 5);

      expect(derived.peg).toBeNull();
      expect(derived.pegError).toContain("negativo");
    });
  });

  describe("pass-through fields", () => {
    it("preserves non-derived fields from full data", () => {
      const full = makeFullData({ years: 5 });
      full.debtToEquity = 1.5;
      full.liabilitiesToEquity = 2.0;
      full.leverageDate = "2025-03-31";
      full.currentPrice = 42;

      const derived = deriveForYears(full, 3);

      expect(derived.ticker).toBe("TEST4");
      expect(derived.name).toBe("Test Co");
      expect(derived.currentPrice).toBe(42);
      expect(derived.debtToEquity).toBe(1.5);
      expect(derived.liabilitiesToEquity).toBe(2.0);
      expect(derived.leverageDate).toBe("2025-03-31");
    });
  });

  describe("CAGR with 1 year", () => {
    it("returns null CAGR when only 1 year of data", () => {
      const full = makeFullData({ years: 10 });
      const derived = deriveForYears(full, 1);

      expect(derived.earningsCAGR).toBeNull();
      expect(derived.fcfCAGR).toBeNull();
    });
  });
});
