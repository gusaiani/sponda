import { describe, it, expect } from "vitest";
import { deriveForYears, effectiveYearsForCompany } from "./deriveForYears";
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
      // Spread the year total evenly across 4 quarters so the trailing-
      // quarters helper has something to sum at quarter granularity. The
      // values themselves are arbitrary — only the per-quarter sum matters.
      quarterlyDetail: [0, 1, 2, 3].map((qIndex) => ({
        end_date: `${currentYear - i}-${String((qIndex + 1) * 3).padStart(2, "0")}-30`,
        net_income: v / 4,
      })),
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
      quarterlyDetail: [0, 1, 2, 3].map((qIndex) => ({
        end_date: `${currentYear - i}-${String((qIndex + 1) * 3).padStart(2, "0")}-30`,
        operating_cash_flow: v / 4,
        investment_cash_flow: 0,
        fcf: v / 4,
      })),
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
    // Liquidity
    currentRatio: null,
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

    it("returns null for year-dependent metrics when requesting more years than available", () => {
      const full = makeFullData({ years: 5 });
      const derived = deriveForYears(full, 20);

      // Strict semantics: if the company has fewer than the requested years of
      // data, year-dependent metrics must be null so the UI can render N/A.
      expect(derived.pe10).toBeNull();
      expect(derived.pfcf10).toBeNull();
      expect(derived.peg).toBeNull();
      expect(derived.pfcfPeg).toBeNull();
      expect(derived.earningsCAGR).toBeNull();
      expect(derived.fcfCAGR).toBeNull();
      expect(derived.debtToAvgEarnings).toBeNull();
      expect(derived.debtToAvgFCF).toBeNull();
      expect(derived.roe).toBeNull();
    });

    it("labels reflect the requested years, not the clipped available years", () => {
      const full = makeFullData({ years: 5 });
      const derived = deriveForYears(full, 20);

      expect(derived.pe10Label).toBe("PE20");
      expect(derived.pfcf10Label).toBe("PFCF20");
    });

    it("returns pe10 as null but keeps pfcf10 when only FCF data is sufficient", () => {
      const full = makeFullData({ years: 5 });
      // Pretend FCF has more years than earnings by extending its array
      full.pfcf10CalculationDetails = Array.from({ length: 10 }, (_, i) => ({
        year: 2025 - i,
        nominalFCF: 80_000,
        ipcaFactor: 1,
        adjustedFCF: 80_000,
        quarters: 4,
        quarterlyDetail: [0, 1, 2, 3].map((qIndex) => ({
          end_date: `${2025 - i}-${String((qIndex + 1) * 3).padStart(2, "0")}-30`,
          operating_cash_flow: 20_000,
          investment_cash_flow: 0,
          fcf: 20_000,
        })),
      }));

      const derived = deriveForYears(full, 7);

      expect(derived.pe10).toBeNull();
      expect(derived.pfcf10).not.toBeNull();
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

    it("computes negative PE10 when average earnings are negative", () => {
      const full = makeFullData({
        years: 3,
        marketCap: 100_000,
        earnings: [-50_000, -50_000, -50_000],
      });
      const derived = deriveForYears(full, 3);

      // avg = -50_000, PE = 100_000 / -50_000 = -2.0
      expect(derived.pe10).toBe(-2.0);
      expect(derived.pe10Error).toBeNull();
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

    it("returns PEG error when PE is negative", () => {
      const full = makeFullData({
        years: 3,
        marketCap: 1_000_000,
        earnings: [-50_000, -50_000, -50_000],
      });
      const derived = deriveForYears(full, 3);

      // PE is negative, so PEG should be null with error
      expect(derived.pe10).toBeLessThan(0);
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
      expect(derived.pegError).toBe("negative_growth");
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

    it("preserves currentRatio from the original quote", () => {
      const full = makeFullData({ years: 5 });
      full.currentRatio = 1.55;

      const derived = deriveForYears(full, 3);

      expect(derived.currentRatio).toBe(1.55);
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

  describe("window-aware ratings", () => {
    it("rates the indicators using the *derived* (sliced) values, not the backend snapshot", () => {
      // Regression for the KEPL3 / PFCLG bug: the chip rated the backend's
      // long-window PFCLG while the card displayed the 10y window PFCLG.
      // Build a quote whose recent decade grows fast (high CAGR → low PFCLG)
      // but whose long history grows slowly (low CAGR → high PFCLG). The
      // chip must follow the displayed value.
      const fcf = [
        // Last 10 years: steady ~10% growth — recent FCF roughly 2.6x oldest-in-window.
        260_000, 236_000, 215_000, 196_000, 178_000,
        162_000, 147_000, 134_000, 122_000, 110_000,
        // Older 10 years: flat ~100k → drags the long-window CAGR down.
        100_000, 100_000, 100_000, 100_000, 100_000,
        100_000, 100_000, 100_000, 100_000, 100_000,
      ];
      const earnings = fcf.map((v) => Math.round(v * 0.9));
      // Market cap chosen so PFCF10 ≈ 7 (low end of "Forte" PFCF10) and
      // PFCLG comes out around 0.7-0.8 for the 10y window.
      const avgFCF10 = fcf.slice(0, 10).reduce((s, v) => s + v, 0) / 10;
      const marketCap = avgFCF10 * 7;

      const full = makeFullData({ years: 20, marketCap, fcf, earnings });
      // Inject a backend snapshot that says PFCLG is Fraco (tier 2).
      full.ratings = {
        pe10: 3, pfcf10: 3, peg: 2, pfcfPeg: 2,
        debtToEquity: null, debtExLeaseToEquity: null,
        liabilitiesToEquity: null, currentRatio: null,
        debtToAvgEarnings: null, debtToAvgFCF: null,
        overall: 2, methodologyVersion: "v1",
      };

      const derived = deriveForYears(full, 10);

      expect(derived.pfcfPeg).not.toBeNull();
      expect(derived.pfcfPeg!).toBeLessThan(1.0);
      expect(derived.ratings).toBeDefined();
      // Derived PFCLG sits in (0.5, 1] → tier 4 (Forte). Backend said 2.
      expect(derived.ratings!.pfcfPeg).toBe(4);
      expect(derived.ratings!.pfcfPeg).not.toBe(full.ratings.pfcfPeg);
    });

    it("emits null tiers when an indicator could not be computed", () => {
      const full = makeFullData({ years: 5 });
      const derived = deriveForYears(full, 20); // requesting more than available → all null

      expect(derived.ratings).toBeDefined();
      expect(derived.ratings!.pe10).toBeNull();
      expect(derived.ratings!.pfcf10).toBeNull();
      expect(derived.ratings!.pfcfPeg).toBeNull();
    });
  });

  describe("trailing N×4 quarters average (partial current year)", () => {
    // TFCO4 (Track & Field) bug regression: latest fiscal year had only Q1
    // reported. Old behaviour summed 3 calendar years (Q1 2026 + full 2025 +
    // full 2024 = 9 quarters) and divided by 3, underestimating the average.
    // New behaviour: trail back into 2023 to gather a full N×4 quarters and
    // divide that sum by N.

    function makePartialCurrentYearQuote(_years: number, marketCap: number): QuoteResult {
      // Year layout (most-recent first), each quarter worth $10:
      //   2026: 1 quarter   (Q1 only)         → $10
      //   2025: 4 quarters                    → $40
      //   2024: 4 quarters                    → $40
      //   2023: 4 quarters                    → $40 (only the tail-3 enter the trailing-12 window)
      // PE3 trailing-12 average = (10 + 40 + 40 + 30) / 3 = $40
      // OLD calendar-year average = (10 + 40 + 40) / 3 = $30 → PE too low.
      const earningsBreakdown = [
        { year: 2026, quartersValues: [10] },
        { year: 2025, quartersValues: [10, 10, 10, 10] },
        { year: 2024, quartersValues: [10, 10, 10, 10] },
        { year: 2023, quartersValues: [10, 10, 10, 10] },
      ];
      const pe10CalculationDetails = earningsBreakdown.map((y) => ({
        year: y.year,
        nominalNetIncome: y.quartersValues.reduce((s, v) => s + v, 0),
        ipcaFactor: 1,
        adjustedNetIncome: y.quartersValues.reduce((s, v) => s + v, 0),
        quarters: y.quartersValues.length,
        quarterlyDetail: y.quartersValues.map((v, i) => ({
          // q1=Mar, q2=Jun, q3=Sep, q4=Dec
          end_date: `${y.year}-${String((i + 1) * 3).padStart(2, "0")}-30`,
          net_income: v,
        })),
      }));
      const pfcf10CalculationDetails = earningsBreakdown.map((y) => ({
        year: y.year,
        nominalFCF: y.quartersValues.reduce((s, v) => s + v, 0),
        ipcaFactor: 1,
        adjustedFCF: y.quartersValues.reduce((s, v) => s + v, 0),
        quarters: y.quartersValues.length,
        quarterlyDetail: y.quartersValues.map((v, i) => ({
          end_date: `${y.year}-${String((i + 1) * 3).padStart(2, "0")}-30`,
          operating_cash_flow: v,
          investment_cash_flow: 0,
          fcf: v,
        })),
      }));
      return {
        ticker: "TFCO4",
        name: "Track & Field",
        logo: "",
        currentPrice: 1,
        marketCap,
        maxYearsAvailable: 4,
        pe10: null, avgAdjustedNetIncome: null, pe10YearsOfData: 0,
        pe10Label: "PE0", pe10Error: null, pe10AnnualData: false,
        pe10CalculationDetails,
        pfcf10: null, avgAdjustedFCF: null, pfcf10YearsOfData: 0,
        pfcf10Label: "PFCF0", pfcf10Error: null, pfcf10AnnualData: false,
        pfcf10CalculationDetails,
        debtToEquity: null, debtExLeaseToEquity: null,
        liabilitiesToEquity: null, currentRatio: null,
        leverageError: null, leverageDate: null,
        totalDebt: null, totalLease: null, totalLiabilities: null,
        stockholdersEquity: null,
        debtToAvgEarnings: null, debtToAvgFCF: null,
        peg: null, earningsCAGR: null, pegError: null,
        earningsCAGRMethod: null, earningsCAGRExcludedYears: [],
        pfcfPeg: null, fcfCAGR: null, pfcfPegError: null,
        fcfCAGRMethod: null, fcfCAGRExcludedYears: [],
        roe: null, priceToBook: null,
      };
    }

    it("averages over the trailing N×4 quarters, not N calendar years", () => {
      const full = makePartialCurrentYearQuote(3, /*marketCap*/ 400);
      const derived = deriveForYears(full, 3);

      // Expected: trailing 12 quarters = 10 (Q1 2026) + 40 (2025) + 40 (2024) + 30 (Q2-Q4 2023)
      // Sum = 120, avg = 40, PE = 400 / 40 = 10
      expect(derived.avgAdjustedNetIncome).toBeCloseTo(40, 5);
      expect(derived.pe10).toBe(10);
    });

    it("includes a synthesized partial-tail year in calculationDetails for display", () => {
      const full = makePartialCurrentYearQuote(3, 400);
      const derived = deriveForYears(full, 3);

      // 4 rows expected: 2026 (1q), 2025 (4q), 2024 (4q), 2023 (synthetic 3q tail)
      expect(derived.pe10CalculationDetails).toHaveLength(4);
      const tail = derived.pe10CalculationDetails[3];
      expect(tail.year).toBe(2023);
      expect(tail.quarters).toBe(3);
      expect(tail.quarterlyDetail).toHaveLength(3);
      // The 3 quarters kept are the most-recent 3 of 2023 (Q2, Q3, Q4)
      expect(tail.quarterlyDetail.map((q) => q.end_date)).toEqual([
        "2023-06-30",
        "2023-09-30",
        "2023-12-30",
      ]);
      // nominal/adjusted reflect the 3 quarters only (not the full year)
      expect(tail.nominalNetIncome).toBe(30);
      expect(tail.adjustedNetIncome).toBe(30);
    });

    it("denominator remains N (slider value), not the number of detail rows", () => {
      const full = makePartialCurrentYearQuote(3, 400);
      const derived = deriveForYears(full, 3);

      // pe10YearsOfData is the divisor displayed in the modal: must be 3.
      expect(derived.pe10YearsOfData).toBe(3);
      expect(derived.pe10Label).toBe("PE3");
    });

    it("does the same for PFCF / FCF average", () => {
      const full = makePartialCurrentYearQuote(3, 400);
      const derived = deriveForYears(full, 3);

      expect(derived.avgAdjustedFCF).toBeCloseTo(40, 5);
      expect(derived.pfcf10).toBe(10);
      expect(derived.pfcf10CalculationDetails).toHaveLength(4);
    });

    it("ROE uses the trailing-quarters average earnings, not the calendar-year sum", () => {
      const full = makePartialCurrentYearQuote(3, 400);
      full.stockholdersEquity = 400;
      const derived = deriveForYears(full, 3);

      // ROE = avgAdjustedNetIncome / equity = 40 / 400 = 10%
      expect(derived.roe).toBe(10);
    });

    it("debt/avgEarnings uses the trailing-quarters average", () => {
      const full = makePartialCurrentYearQuote(3, 400);
      full.totalDebt = 80;
      const derived = deriveForYears(full, 3);

      // debt / avg = 80 / 40 = 2.0
      expect(derived.debtToAvgEarnings).toBe(2.0);
    });

    it("returns null when there aren't enough quarters for the requested window", () => {
      // 4 calendar years total = 13 quarters (one of them partial).
      // Asking for 5 years (= 20 quarters) → insufficient.
      const full = makePartialCurrentYearQuote(3, 400);
      const derived = deriveForYears(full, 5);

      expect(derived.pe10).toBeNull();
      expect(derived.avgAdjustedNetIncome).toBeNull();
    });

    it("excludes partial-current and partial-tail years from the CAGR input", () => {
      // Earnings double across the 3 full years (2023→2024→2025 doubles
      // each year), with a partial Q1 2026 that, if naively included,
      // would crash the YoY rate. We expect CAGR to ignore both partial
      // rows and compute growth across the 3 full years only.
      const earningsBreakdown = [
        { year: 2026, quartersValues: [5] },          // partial — should be dropped
        { year: 2025, quartersValues: [40, 40, 40, 40] }, // = 160
        { year: 2024, quartersValues: [20, 20, 20, 20] }, // = 80
        { year: 2023, quartersValues: [10, 10, 10, 10] }, // = 40 (full)
        { year: 2022, quartersValues: [10, 10, 10, 10] }, // = 40 (full, used as the trailing tail partial)
      ];
      const detailsForBoth = earningsBreakdown.map((y) => ({
        year: y.year,
        nominalNetIncome: y.quartersValues.reduce((s, v) => s + v, 0),
        ipcaFactor: 1,
        adjustedNetIncome: y.quartersValues.reduce((s, v) => s + v, 0),
        quarters: y.quartersValues.length,
        quarterlyDetail: y.quartersValues.map((v, i) => ({
          end_date: `${y.year}-${String((i + 1) * 3).padStart(2, "0")}-30`,
          net_income: v,
        })),
      }));
      const full = makeFullData({ years: 1 });
      full.pe10CalculationDetails = detailsForBoth;
      full.maxYearsAvailable = 5;

      const derived = deriveForYears(full, 3);

      // Sliced detail (most-recent first): 2026(partial), 2025, 2024,
      // and a synthesised 2023 with 3 quarters (3 × $10 = $30).
      // CAGR input after filtering: only 2025 + 2024 (both full, in window).
      // Endpoint CAGR over 1 year = 160 / 80 = 2.0 → +100%.
      expect(derived.earningsCAGR).toBeCloseTo(100, 1);
    });

    it("falls through unchanged when every year in the window is already full", () => {
      // No partial-current-year — the slicing should match the old behaviour.
      const full = makeFullData({ years: 5, marketCap: 500_000, earnings: [100_000, 100_000, 100_000, 100_000, 100_000] });
      const derived = deriveForYears(full, 5);

      expect(derived.pe10).toBe(5);
      expect(derived.pe10CalculationDetails).toHaveLength(5);
      // No synthetic partial row appended
      expect(derived.pe10CalculationDetails.every((row) => row.quarters === 4)).toBe(true);
    });
  });
});

describe("effectiveYearsForCompany", () => {
  it("returns the slider value when the company has at least that many years", () => {
    expect(effectiveYearsForCompany(10, 17)).toBe(10);
    expect(effectiveYearsForCompany(10, 10)).toBe(10);
  });

  it("caps to the company's maximum when the slider exceeds it", () => {
    // Duolingo case: slider at 10y, only ~4 years of history.
    expect(effectiveYearsForCompany(10, 4)).toBe(4);
    expect(effectiveYearsForCompany(20, 6)).toBe(6);
  });

  it("falls back to the slider value when maxAvailable is null or undefined", () => {
    expect(effectiveYearsForCompany(10, null)).toBe(10);
    expect(effectiveYearsForCompany(10, undefined)).toBe(10);
  });

  it("never returns less than 1", () => {
    expect(effectiveYearsForCompany(10, 0)).toBe(1);
    expect(effectiveYearsForCompany(10, -5)).toBe(1);
  });
});
