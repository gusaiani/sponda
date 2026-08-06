// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { CompanyMetricsCard } from "./CompanyMetricsCard";

vi.mock("../i18n", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    pluralize: (key: string) => key,
    locale: "en",
  }),
}));
vi.mock("./AlertButton", () => ({ AlertButton: () => null }));
vi.mock("./RatingChip", () => ({ RatingChip: () => null }));
vi.mock("../hooks/useComparisonSeries", () => ({
  useComparisonSeries: () => [],
}));
vi.mock("../hooks/useFxSeries", () => ({
  useFxSeriesMany: () => ({}),
}));
vi.mock("../hooks/useTickerSearch", () => ({
  useTickerSearch: () => ({ results: [] }),
}));

afterEach(cleanup);

const CURRENT_YEAR = new Date().getFullYear();

function yearlyEarnings(year: number) {
  return {
    year,
    nominalNetIncome: 1000,
    ipcaFactor: 1,
    adjustedNetIncome: 1000,
    quarters: 4,
    quarterlyDetail: [],
  };
}

function yearlyFCF(year: number) {
  return {
    year,
    nominalFCF: 800,
    ipcaFactor: 1,
    adjustedFCF: 800,
    quarters: 4,
    quarterlyDetail: [],
  };
}

function makeQuote(years: number) {
  const detailYears = Array.from({ length: 6 }, (_, i) => CURRENT_YEAR - i);
  return {
    ticker: "TEST",
    name: "TestCo",
    logo: "",
    currentPrice: 10,
    marketCap: 10000,
    pe10: 10,
    avgAdjustedNetIncome: 1000,
    pe10YearsOfData: years,
    pe10Label: `PE${years}`,
    pe10Error: null,
    pe10AnnualData: false,
    pe10CalculationDetails: detailYears.map(yearlyEarnings),
    pfcf10: 12.5,
    avgAdjustedFCF: 800,
    pfcf10YearsOfData: years,
    pfcf10Label: `PFCF${years}`,
    pfcf10Error: null,
    pfcf10AnnualData: false,
    pfcf10CalculationDetails: detailYears.map(yearlyFCF),
    maxYearsAvailable: 20,
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
  };
}

const priceHistory = [
  { date: `${CURRENT_YEAR - 1}-03-01`, adjustedClose: 8 },
  { date: `${CURRENT_YEAR - 1}-09-01`, adjustedClose: 9 },
  { date: `${CURRENT_YEAR}-02-01`, adjustedClose: 10 },
  { date: `${CURRENT_YEAR}-06-01`, adjustedClose: 11 },
];

function renderCard(years: number) {
  return render(
    <CompanyMetricsCard
      data={makeQuote(years)}
      years={years}
      maxYears={20}
      onYearsChange={() => {}}
      priceHistory={priceHistory}
    />,
  );
}

describe("CompanyMetricsCard expanded chart", () => {
  it("updates the modal title when the term changes while the chart is open", () => {
    const { container, rerender } = renderCard(5);

    const expandButton = container.querySelector("#pe10 .expand-btn");
    expect(expandButton).not.toBeNull();
    fireEvent.click(expandButton!);
    expect(screen.getByText("PE5 — TestCo")).toBeTruthy();

    rerender(
      <CompanyMetricsCard
        data={makeQuote(13)}
        years={13}
        maxYears={20}
        onYearsChange={() => {}}
        priceHistory={priceHistory}
      />,
    );

    expect(screen.getByText("PE13 — TestCo")).toBeTruthy();
  });
});
