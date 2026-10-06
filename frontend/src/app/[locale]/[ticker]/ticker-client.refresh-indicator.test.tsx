/**
 * While a background statement refresh is in flight the company header
 * says so, and the page hands the hook one verdict built from all three
 * payloads, since any of them may be the one the server flagged.
 *
 * The status poll itself is covered by useStatementRefresh.test.tsx. Here
 * the hook is replaced, so these tests only pin what the page feeds it and
 * what it renders from the answer.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderToString } from "react-dom/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const mocks = vi.hoisted(() => ({
  isRefreshing: false,
  fundamentalsData: undefined as { refreshPending?: boolean } | undefined,
  historyData: undefined as { refreshPending?: boolean } | undefined,
  useStatementRefresh: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ ticker: "PAM" }),
  usePathname: () => "/en/PAM",
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("next/link", () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

vi.mock("next/dynamic", () => ({
  default: () => function DynamicPlaceholder() {
    return null;
  },
}));

vi.mock("../../../i18n", () => ({
  useTranslation: () => ({ t: (key: string) => key, locale: "en" }),
}));

vi.mock("../../../learning", () => ({
  useLearningMode: () => ({ enabled: false }),
}));

vi.mock("../../../components/assistant/AssistantWindowContext", () => ({
  useSetAssistantWindow: () => vi.fn(),
}));

vi.mock("../../../components/FavoriteButton", () => ({ FavoriteButton: () => null }));
vi.mock("../../../components/VisitedButton", () => ({ VisitedButton: () => null }));
vi.mock("../../../components/RevisitBanner", () => ({ RevisitBanner: () => null }));
vi.mock("../../../components/ShareButtons", () => ({ ShareButtons: () => null }));
vi.mock("../../../components/CompanyGradeCard", () => ({ CompanyGradeCard: () => null }));
vi.mock("../../../components/AuthModal", () => ({ AuthModal: () => null }));
vi.mock("../../../components/TabPills", () => ({ TabPills: () => null }));
vi.mock("../../../components/YearsSlider", () => ({ YearsSlider: () => null }));
vi.mock("../../../components/InflationToggle", () => ({ InflationToggle: () => null }));
vi.mock("../../../components/social/SpondsTab", () => ({ SpondsTab: () => null }));

vi.mock("../../../hooks/useTickerDetail", () => ({
  useTickerDetail: () => ({ data: undefined }),
}));
vi.mock("../../../hooks/usePeers", () => ({
  usePeers: () => ({ data: [] }),
}));
vi.mock("../../../hooks/useFundamentals", () => ({
  useFundamentals: () => ({ data: mocks.fundamentalsData }),
  fetchFundamentals: vi.fn(),
}));
vi.mock("../../../hooks/useSavedLists", () => ({
  useSavedLists: () => ({ lists: [] }),
}));
vi.mock("../../../hooks/useMultiplesHistory", () => ({
  useMultiplesHistory: () => ({ data: mocks.historyData, error: null }),
  fetchMultiplesHistory: vi.fn(),
}));
vi.mock("../../../hooks/useStatementRefresh", () => ({
  useStatementRefresh: (ticker: string, isRefreshPending: boolean) => {
    mocks.useStatementRefresh(ticker, isRefreshPending);
    return { isRefreshing: mocks.isRefreshing };
  },
}));

import { TickerPageClient } from "./ticker-client";
import type { QuoteResult } from "../../../hooks/usePE10";

const INDICATOR_TEXT_KEY = "header.updatingData";

function buildQuote(refreshPending?: boolean): QuoteResult {
  return {
    ticker: "PAM",
    name: "Pampa Energía",
    logo: "",
    currentPrice: 10,
    marketCap: 1_000_000,
    maxYearsAvailable: 10,
    pe10: null, avgAdjustedNetIncome: null, pe10YearsOfData: 0, pe10Label: "PE10", pe10Error: null,
    pe10CalculationDetails: [], pe10AnnualData: false,
    pfcf10: null, avgAdjustedFCF: null, pfcf10Error: null,
    pfcf10CalculationDetails: [], pfcf10AnnualData: false,
    debtToEquity: null, debtExLeaseToEquity: null, liabilitiesToEquity: null, currentRatio: null,
    leverageError: null, leverageDate: null,
    totalDebt: null, totalLease: null, totalLiabilities: null, stockholdersEquity: null,
    debtToAvgEarnings: null, debtToAvgFCF: null,
    peg: null, earningsCAGR: null, pegError: null,
    earningsCAGRMethod: null, earningsCAGRExcludedYears: [],
    pfcfPeg: null, fcfCAGR: null, pfcfPegError: null,
    fcfCAGRMethod: null, fcfCAGRExcludedYears: [],
    roe: null, priceToBook: null,
    refreshPending,
  } as unknown as QuoteResult;
}

function renderCompanyPage(quote: QuoteResult | null): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return renderToString(
    <QueryClientProvider client={queryClient}>
      <TickerPageClient initialData={quote} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  mocks.isRefreshing = false;
  mocks.fundamentalsData = undefined;
  mocks.historyData = undefined;
  mocks.useStatementRefresh.mockClear();
});

describe("company header refresh indicator", () => {
  it("shows a status next to the ticker while the statements refresh", () => {
    mocks.isRefreshing = true;

    const html = renderCompanyPage(buildQuote(true));

    expect(html).toMatch(
      new RegExp(`<span[^>]*role="status"[^>]*>[^<]*${INDICATOR_TEXT_KEY}`),
    );
  });

  it("keeps the indicator out of the h1, so the page title stays the company name", () => {
    mocks.isRefreshing = true;

    const html = renderCompanyPage(buildQuote(true));

    const headingMarkup = html.match(/<h1[\s\S]*?<\/h1>/)?.[0] ?? "";
    expect(headingMarkup).not.toContain(INDICATOR_TEXT_KEY);
  });

  it("shows nothing when no refresh is in flight", () => {
    const html = renderCompanyPage(buildQuote(false));

    expect(html).not.toContain(INDICATOR_TEXT_KEY);
    expect(html).not.toContain('role="status"');
  });
});

describe("page wiring of the statement refresh", () => {
  it("is not pending when none of the payloads is flagged", () => {
    renderCompanyPage(buildQuote(false));

    expect(mocks.useStatementRefresh).toHaveBeenLastCalledWith("PAM", false);
  });

  it("is not pending when the payloads predate the flag", () => {
    renderCompanyPage(buildQuote(undefined));

    expect(mocks.useStatementRefresh).toHaveBeenLastCalledWith("PAM", false);
  });

  it("is pending when the quote is flagged", () => {
    renderCompanyPage(buildQuote(true));

    expect(mocks.useStatementRefresh).toHaveBeenLastCalledWith("PAM", true);
  });

  it("is pending when only the fundamentals payload is flagged", () => {
    mocks.fundamentalsData = { refreshPending: true };

    renderCompanyPage(buildQuote(false));

    expect(mocks.useStatementRefresh).toHaveBeenLastCalledWith("PAM", true);
  });

  it("is pending when only the multiples history payload is flagged", () => {
    mocks.historyData = { refreshPending: true };

    renderCompanyPage(buildQuote(false));

    expect(mocks.useStatementRefresh).toHaveBeenLastCalledWith("PAM", true);
  });
});
