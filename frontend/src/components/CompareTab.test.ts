import { describe, it, expect } from "vitest";
import { getColumns, type CompareRowData } from "./CompareTab";
import type { QuoteResult } from "../hooks/usePE10";
import type { FundamentalsYear } from "../hooks/useFundamentals";
import { pt } from "../i18n/locales/pt";
import { en } from "../i18n/locales/en";
import type { TranslationKey } from "../i18n";

const t = (key: TranslationKey) => pt[key];
const tEn = (key: TranslationKey) => en[key];

function makeQuoteResult(overrides: Partial<QuoteResult> = {}): QuoteResult {
  return {
    ticker: "TEST3",
    name: "Test Company",
    logo: "",
    currentPrice: 10,
    marketCap: null,
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

function makeFundamentalsYear(overrides: Partial<FundamentalsYear> = {}): FundamentalsYear {
  return {
    year: 2024,
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

function makeRowData(
  quoteOverrides: Partial<QuoteResult> = {},
  recentOverrides: Partial<FundamentalsYear> | null = {},
): CompareRowData {
  return {
    quote: makeQuoteResult(quoteOverrides),
    recent: recentOverrides === null ? null : makeFundamentalsYear(recentOverrides),
    pe: null,
    pfcf: null,
  };
}

describe("getColumns", () => {
  it("returns 14 columns mirroring fundamentals", () => {
    expect(getColumns(5, t)).toHaveLength(14);
  });

  it("groups columns into balance (6), income (3), cash flow (3), returns (2)", () => {
    const columns = getColumns(5, t);
    expect(columns.filter((c) => c.group === "balanco")).toHaveLength(6);
    expect(columns.filter((c) => c.group === "resultado")).toHaveLength(3);
    expect(columns.filter((c) => c.group === "caixa")).toHaveLength(3);
    expect(columns.filter((c) => c.group === "retorno")).toHaveLength(2);
  });

  it("includes the year suffix in PE and PFCF labels (PT)", () => {
    const columns = getColumns(7, t);
    const labels = columns.map((c) => c.label);
    expect(labels).toContain("P/L7");
    expect(labels).toContain("P/FCL7");
  });

  it("includes the year suffix in PE and PFCF labels (EN)", () => {
    const columns = getColumns(7, tEn);
    const labels = columns.map((c) => c.label);
    expect(labels).toContain("PE7");
    expect(labels).toContain("PFCF7");
  });

  it("uses fundamentals i18n keys for fixed labels", () => {
    const columns = getColumns(5, t);
    const labels = columns.map((c) => c.label);
    expect(labels).toContain("Dívida (M)");
    expect(labels).toContain("Passivo (M)");
    expect(labels).toContain("PL (M)");
    expect(labels).toContain("Dív/PL");
    expect(labels).toContain("Pass/PL");
    expect(labels).toContain("Liq. Corr.");
    expect(labels).toContain("Receita (M)");
    expect(labels).toContain("Lucro (M)");
    expect(labels).toContain("FCL (M)");
    expect(labels).toContain("FC Oper. (M)");
    expect(labels).toContain("Cap. Mercado (M)");
    expect(labels).toContain("Proventos (M)");
  });

  it("format() returns null when all data fields are null", () => {
    const columns = getColumns(5, t);
    const rowData = makeRowData();
    for (const column of columns) {
      expect(column.format(rowData)).toBeNull();
    }
  });

  it("formats balance values from the most recent fundamentals year", () => {
    const columns = getColumns(5, t);
    const rowData = makeRowData(
      {},
      {
        debtExLease: 5_000_000_000,
        totalLiabilities: 12_000_000_000,
        stockholdersEquity: 8_000_000_000,
        debtToEquity: 0.625,
        liabilitiesToEquity: 1.5,
        currentRatio: 1.8,
      },
    );

    const debt = columns.find((c) => c.key === "debtExLease")!;
    const liab = columns.find((c) => c.key === "totalLiabilities")!;
    const equity = columns.find((c) => c.key === "equity")!;

    expect(debt.format(rowData)).not.toBeNull();
    expect(liab.format(rowData)).not.toBeNull();
    expect(equity.format(rowData)).not.toBeNull();

    expect(columns.find((c) => c.key === "debtToEquity")!.value(rowData)).toBe(0.625);
    expect(columns.find((c) => c.key === "liabToEquity")!.value(rowData)).toBe(1.5);
    expect(columns.find((c) => c.key === "currentRatio")!.value(rowData)).toBe(1.8);
  });

  it("formats income values from the most recent fundamentals year", () => {
    const columns = getColumns(5, t);
    const rowData = makeRowData(
      {},
      { revenue: 10_000_000_000, netIncome: 2_000_000_000 },
    );
    rowData.pe = 12.5;

    const revenue = columns.find((c) => c.key === "revenue")!;
    const netIncome = columns.find((c) => c.key === "netIncome")!;
    const pe = columns.find((c) => c.key === "pe")!;

    expect(revenue.value(rowData)).toBe(10_000_000_000);
    expect(netIncome.value(rowData)).toBe(2_000_000_000);
    expect(pe.value(rowData)).toBe(12.5);
  });

  it("formats cash flow values from the most recent fundamentals year", () => {
    const columns = getColumns(5, t);
    const rowData = makeRowData(
      {},
      { fcf: 1_500_000_000, operatingCashFlow: 2_500_000_000 },
    );
    rowData.pfcf = 8.4;

    expect(columns.find((c) => c.key === "fcf")!.value(rowData)).toBe(1_500_000_000);
    expect(columns.find((c) => c.key === "pfcf")!.value(rowData)).toBe(8.4);
    expect(columns.find((c) => c.key === "operatingCF")!.value(rowData)).toBe(2_500_000_000);
  });

  it("formats market cap from the quote (today's value)", () => {
    const columns = getColumns(5, t);
    const rowData = makeRowData(
      { marketCap: 200_000_000_000 },
      { marketCap: 150_000_000_000 }, // would be different historic value
    );
    const marketCap = columns.find((c) => c.key === "marketCap")!;
    expect(marketCap.value(rowData)).toBe(200_000_000_000);
  });

  it("formats dividends from the most recent fundamentals year", () => {
    const columns = getColumns(5, t);
    const rowData = makeRowData({}, { dividendsPaid: 500_000_000 });
    expect(columns.find((c) => c.key === "dividends")!.value(rowData)).toBe(500_000_000);
  });

  it("returns null for fundamentals-derived columns when recent year is missing", () => {
    const columns = getColumns(5, t);
    const rowData = makeRowData({ marketCap: 100 }, null);

    for (const column of columns) {
      if (column.key === "marketCap") continue; // sourced from quote
      expect(column.value(rowData)).toBeNull();
    }
  });
});
