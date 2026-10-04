// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, cleanup, screen } from "@testing-library/react";
import { FundamentalsTab, type TrailingRatioSource } from "./FundamentalsTab";
import { useFundamentals, type FundamentalsYear } from "../hooks/useFundamentals";

afterEach(cleanup);

vi.mock("../hooks/useFundamentals", () => ({ useFundamentals: vi.fn() }));
vi.mock("../i18n", async () => {
  const { translatorFor } = await import("../i18n/dictionaries");
  return { useTranslation: () => ({ t: translatorFor("pt"), locale: "pt" }) };
});

const NEGATIVE_EARNINGS_YEAR = 2024;

function makeFundamentalsYear(): FundamentalsYear {
  return {
    year: NEGATIVE_EARNINGS_YEAR,
    quarters: 4,
    balanceSheetDate: null,
    marketCap: 500,
    marketCapAdjusted: 500,
    totalDebt: 100,
    totalLease: 0,
    debtExLease: 100,
    debtExLeaseAdjusted: 100,
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
    netIncome: -100,
    netIncomeAdjusted: -100,
    fcf: -50,
    fcfAdjusted: -50,
    operatingCashFlow: null,
    operatingCashFlowAdjusted: null,
    dividendsPaid: null,
    dividendsAdjusted: null,
    ipcaFactor: 1,
  };
}

function makeLossMakingQuote(): TrailingRatioSource {
  const quarterEnds = ["03-31", "06-30", "09-30", "12-31"].map(
    (monthDay) => `${NEGATIVE_EARNINGS_YEAR}-${monthDay}`,
  );
  return {
    pe10PeriodsPerYear: 4,
    pfcf10PeriodsPerYear: 4,
    pe10CalculationDetails: [{
      year: NEGATIVE_EARNINGS_YEAR,
      ipcaFactor: 1,
      quarters: 4,
      quarterlyDetail: quarterEnds.map((end_date) => ({ end_date, net_income: -25 })),
    }],
    pfcf10CalculationDetails: [{
      year: NEGATIVE_EARNINGS_YEAR,
      ipcaFactor: 1,
      quarters: 4,
      quarterlyDetail: quarterEnds.map((end_date) => ({ end_date, fcf: -12.5 })),
    }],
  };
}

describe("FundamentalsTab blank ratio cells", () => {
  it("explains on hover why debt coverage is blank for a loss-making window", () => {
    vi.mocked(useFundamentals).mockReturnValue({
      data: { years: [makeFundamentalsYear()], quarterlyRatios: [] },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useFundamentals>);

    render(
      <FundamentalsTab ticker="COGN3" years={1} valueMode="adjusted" quote={makeLossMakingQuote()} />,
    );

    const earningsCell = screen.getByTitle("Lucro médio negativo na janela: dívida/lucro não se aplica");
    const cashFlowCell = screen.getByTitle("FCL médio negativo na janela: dívida/FCL não se aplica");
    expect(earningsCell.textContent).toBe("lucro neg.");
    expect(cashFlowCell.textContent).toBe("FCL neg.");
    expect(earningsCell.className).toBe("fundamentals-null fundamentals-null-reason");
  });
});
