import { describe, it, expect } from "vitest";
import { getColumns } from "./CompareTab";
import type { QuoteResult } from "../hooks/usePE10";
import { pt } from "../i18n/locales/pt";
import type { TranslationKey } from "../i18n";

const t = (key: TranslationKey) => pt[key];

function makeQuoteResult(overrides: Partial<QuoteResult> = {}): QuoteResult {
  return {
    ticker: "TEST3",
    name: "Test Company",
    logo: "https://example.com/logo.png",
    currentPrice: 10,
    marketCap: 1000,
    maxYearsAvailable: 10,
    pe10: null,
    avgAdjustedNetIncome: null,
    pe10YearsOfData: 0,
    pe10Label: "P/L10",
    pe10Error: null,
    pe10AnnualData: false,
    pe10CalculationDetails: [],
    pfcf10: null,
    avgAdjustedFCF: null,
    pfcf10YearsOfData: 0,
    pfcf10Label: "P/FCL10",
    pfcf10Error: null,
    pfcf10AnnualData: false,
    pfcf10CalculationDetails: [],
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
    ...overrides,
  };
}

describe("getColumns", () => {
  it("returns 14 columns", () => {
    const columns = getColumns(5, t);
    expect(columns).toHaveLength(14);
  });

  it("includes the year number in dynamic labels", () => {
    const columns = getColumns(5, t);
    const labels = columns.map((column) => column.label);

    expect(labels).toContain("Dív/Lucro5");
    expect(labels).toContain("Dív/FCL5");
    expect(labels).toContain("ROE5");
    expect(labels).toContain("P/L5");
    expect(labels).toContain("P/FCL5");
    expect(labels).toContain("PEG5");
    expect(labels).toContain("PFCLG5");
    expect(labels).toContain("CAGR L5");
    expect(labels).toContain("CAGR FCL5");
  });

  it("uses different year number when years changes", () => {
    const columns = getColumns(10, t);
    const labels = columns.map((column) => column.label);

    expect(labels).toContain("Dív/Lucro10");
    expect(labels).toContain("ROE10");
    expect(labels).toContain("PEG10");
  });

  it("keeps fixed labels unchanged regardless of years", () => {
    const columnsWith5 = getColumns(5, t);
    const columnsWith10 = getColumns(10, t);

    const fixedLabels = ["Dív/PL", "Dív-Arr/PL", "Pass/PL", "Liq. Corr.", "P/VPA"];

    for (const label of fixedLabels) {
      expect(columnsWith5.map((c) => c.label)).toContain(label);
      expect(columnsWith10.map((c) => c.label)).toContain(label);
    }
  });

  it("uses English labels when given English translations", async () => {
    const { en } = await import("../i18n/locales/en");
    const tEn = (key: TranslationKey) => en[key];
    const columns = getColumns(10, tEn);
    const labels = columns.map((c) => c.label);

    expect(labels).toContain("D/E");
    expect(labels).toContain("D-Lease/E");
    expect(labels).toContain("L/E");
    expect(labels).toContain("Curr. Ratio");
    expect(labels).toContain("P/B");
    expect(labels).toContain("D/Earn10");
    expect(labels).toContain("P/E10");
    expect(labels).toContain("PEG10");
    expect(labels).toContain("CAGR E10");
  });

  it("has 6 endividamento, 2 rentabilidade, and 6 valuation columns", () => {
    const columns = getColumns(5, t);

    const endividamento = columns.filter((column) => column.group === "endividamento");
    const rentabilidade = columns.filter((column) => column.group === "rentabilidade");
    const valuation = columns.filter((column) => column.group === "valuation");

    expect(endividamento).toHaveLength(6);
    expect(rentabilidade).toHaveLength(2);
    expect(valuation).toHaveLength(6);
  });

  it("format() returns null when the field is null", () => {
    const columns = getColumns(5, t);
    const quoteResult = makeQuoteResult();

    for (const column of columns) {
      expect(column.format(quoteResult)).toBeNull();
    }
  });

  it("format() returns a formatted string when field has a value", () => {
    const columns = getColumns(5, t);
    const quoteResult = makeQuoteResult({
      debtToEquity: 1.5,
      debtExLeaseToEquity: 0.8,
      liabilitiesToEquity: 2.3,
      debtToAvgEarnings: 3.7,
      debtToAvgFCF: 4.2,
      currentRatio: 1.25,
      roe: 15.3,
      priceToBook: 2.1,
      pe10: 12.5,
      pfcf10: 8.3,
      peg: 1.45,
      pfcfPeg: 0.92,
      earningsCAGR: 10.5,
      fcfCAGR: 8.7,
    });

    for (const column of columns) {
      const formatted = column.format(quoteResult);
      expect(formatted).not.toBeNull();
      expect(typeof formatted).toBe("string");
    }

    // Verify percentage formatting for ROE
    const roeColumn = columns.find((column) => column.key === "roe")!;
    expect(roeColumn.format(quoteResult)).toContain("%");

    // Verify percentage formatting for CAGR columns
    const earningsCAGRColumn = columns.find((column) => column.key === "earningsCAGR")!;
    expect(earningsCAGRColumn.format(quoteResult)).toContain("%");

    const fcfCAGRColumn = columns.find((column) => column.key === "fcfCAGR")!;
    expect(fcfCAGRColumn.format(quoteResult)).toContain("%");
  });

  it("value() extracts the raw number from the quote result", () => {
    const columns = getColumns(5, t);
    const quoteResult = makeQuoteResult({
      debtToEquity: 1.5,
      pe10: 12.5,
      roe: 15.3,
      peg: 1.45,
    });

    const debtToEquityColumn = columns.find((column) => column.key === "debtToEquity")!;
    expect(debtToEquityColumn.value(quoteResult)).toBe(1.5);

    const pe10Column = columns.find((column) => column.key === "pe10")!;
    expect(pe10Column.value(quoteResult)).toBe(12.5);

    const roeColumn = columns.find((column) => column.key === "roe")!;
    expect(roeColumn.value(quoteResult)).toBe(15.3);

    const pegColumn = columns.find((column) => column.key === "peg")!;
    expect(pegColumn.value(quoteResult)).toBe(1.45);
  });

  it("value() returns null when the field is null", () => {
    const columns = getColumns(5, t);
    const quoteResult = makeQuoteResult();

    for (const column of columns) {
      expect(column.value(quoteResult)).toBeNull();
    }
  });
});
