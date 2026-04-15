// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, cleanup } from "@testing-library/react";
import { CompanyCard } from "./HomepageCompanyCards";
import type { QuoteResult } from "../hooks/usePE10";

afterEach(cleanup);

vi.mock("../i18n", () => ({
  useTranslation: () => ({
    // Map keys to realistic pt labels so we can assert the suffixed output
    t: (key: string) => {
      const dict: Record<string, string> = {
        "homepage.price": "Preço",
        "homepage.market_cap": "Valor de mercado",
        "homepage.equity": "PL",
        "homepage.liabilities": "Passivos",
        "homepage.gross_debt": "Dívida bruta",
        "homepage.current_ratio": "Liq. corrente",
        "homepage.debt_fcf": "Dív / FCL",
        "homepage.price_to_book": "P/VPA",
        "homepage.cagr_earnings_short": "CAGR L",
        "homepage.cagr_fcf_short": "CAGR FCL",
        "fundamentals.col.debt_equity": "Dív / PL",
        "compare.col_pe": "P/L",
        "compare.col_pfcf": "P/FCL",
        "compare.col_peg": "PEG",
        "compare.col_pfcf_peg": "PFCLG",
        "compare.col_cagr_earnings": "CAGR L",
        "compare.col_cagr_fcf": "CAGR FCL",
        "compare.col_roe": "ROE",
      };
      return dict[key] ?? key;
    },
    locale: "pt",
  }),
}));

function makeQuote(overrides: Partial<QuoteResult> = {}): QuoteResult {
  return {
    ticker: "PETR4",
    name: "Petrobras",
    logo: "",
    currentPrice: 30,
    marketCap: 500_000_000_000,
    maxYearsAvailable: 10,
    pe10: 5.5,
    avgAdjustedNetIncome: 100_000_000_000,
    pe10YearsOfData: 10,
    pe10Label: "PE10",
    pe10Error: null,
    pe10AnnualData: false,
    pe10CalculationDetails: [],
    pfcf10: 7.2,
    avgAdjustedFCF: 70_000_000_000,
    pfcf10YearsOfData: 10,
    pfcf10Label: "PFCF10",
    pfcf10Error: null,
    pfcf10AnnualData: false,
    pfcf10CalculationDetails: [],
    debtToEquity: 0.5,
    debtExLeaseToEquity: 0.4,
    liabilitiesToEquity: 1.2,
    currentRatio: 1.5,
    leverageError: null,
    leverageDate: null,
    totalDebt: 100_000_000_000,
    totalLease: 10_000_000_000,
    totalLiabilities: 300_000_000_000,
    stockholdersEquity: 200_000_000_000,
    debtToAvgEarnings: 1.0,
    debtToAvgFCF: 1.4,
    peg: 0.5,
    earningsCAGR: 12.3,
    pegError: null,
    earningsCAGRMethod: "endpoint",
    earningsCAGRExcludedYears: [],
    pfcfPeg: 0.6,
    fcfCAGR: 10.1,
    pfcfPegError: null,
    fcfCAGRMethod: "endpoint",
    fcfCAGRExcludedYears: [],
    roe: 15.0,
    priceToBook: 1.2,
    ...overrides,
  };
}

function labelTexts(): string[] {
  return Array.from(document.querySelectorAll(".hcc-indicator-label")).map(
    (element) => (element.textContent ?? "").trim(),
  );
}

describe("CompanyCard dynamic labels", () => {
  it("suffixes year-dependent labels with the active years value", () => {
    render(<CompanyCard data={makeQuote()} isLoading={false} years={7} />);

    const labels = labelTexts();
    expect(labels).toContain("P/L7");
    expect(labels).toContain("P/FCL7");
    expect(labels).toContain("PEG7");
    expect(labels).toContain("PFCLG7");
    expect(labels).toContain("CAGR L7");
    expect(labels).toContain("CAGR FCL7");
  });

  it("updates labels when years changes", () => {
    render(<CompanyCard data={makeQuote()} isLoading={false} years={12} />);

    const labels = labelTexts();
    expect(labels).toContain("P/L12");
    expect(labels).toContain("P/FCL12");
    expect(labels).toContain("PEG12");
    expect(labels).toContain("PFCLG12");
  });

  it("renders N/A ('·') for year-dependent metrics when the value is null", () => {
    const data = makeQuote({
      pe10: null,
      pfcf10: null,
      peg: null,
      pfcfPeg: null,
      earningsCAGR: null,
      fcfCAGR: null,
      debtToAvgFCF: null,
      roe: null,
    });
    render(<CompanyCard data={data} isLoading={false} years={10} />);

    const indicators = document.querySelectorAll(".hcc-indicator-value");
    const naCount = Array.from(indicators).filter(
      (element) => (element.textContent ?? "").trim() === "·",
    ).length;

    // At least the 8 year-dependent metrics above should render as N/A
    expect(naCount).toBeGreaterThanOrEqual(8);
  });
});
