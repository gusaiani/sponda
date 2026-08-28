/**
 * The ticker page must render the same markup on the server as it does on
 * the browser's very first pass.
 *
 * JAVASCRIPT-NEXTJS-2 (hydration) and JAVASCRIPT-NEXTJS-5 (`removeChild`)
 * both fired on `/:locale/:ticker`, and both come from the same divergence.
 * React Query reports a pending query as `isLoading: false` while the
 * persisted cache is being restored, because restoring forces `fetchStatus`
 * to `idle`. Only the browser restores anything, since the server has no
 * persister, so a query with no `initialData` reports:
 *
 *     server           isLoading: true
 *     first client render   isLoading: false
 *
 * Any markup gated on `isLoading` therefore differs before a single effect
 * has run. The page must gate on the data it actually has instead, which
 * both sides start from.
 */
import { describe, expect, it, vi } from "vitest";
import { renderToString } from "react-dom/server";
import {
  IsRestoringProvider,
  QueryClient,
  QueryClientProvider,
  useQuery,
} from "@tanstack/react-query";

const mockPathname = vi.hoisted(() => ({ current: "/en/PAM" }));

vi.mock("next/navigation", () => ({
  useParams: () => ({ ticker: "PAM" }),
  usePathname: () => mockPathname.current,
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

vi.mock("../../../components/FavoriteButton", () => ({
  FavoriteButton: () => <button type="button">favorite</button>,
}));
vi.mock("../../../components/VisitedButton", () => ({
  VisitedButton: () => <button type="button">visited</button>,
}));
vi.mock("../../../components/RevisitBanner", () => ({
  RevisitBanner: () => <div className="revisit-banner" />,
}));
vi.mock("../../../components/ShareButtons", () => ({
  ShareButtons: () => <div className="share-buttons" />,
}));
vi.mock("../../../components/CompanyGradeCard", () => ({
  CompanyGradeCard: () => <span className="company-grade-card" />,
}));
vi.mock("../../../components/AuthModal", () => ({
  AuthModal: () => <div className="auth-modal" />,
}));
vi.mock("../../../components/TabPills", () => ({
  TabPills: () => <div className="tab-pills" />,
}));
vi.mock("../../../components/YearsSlider", () => ({
  YearsSlider: () => <div className="years-slider" />,
}));
vi.mock("../../../components/InflationToggle", () => ({
  InflationToggle: () => <div className="inflation-toggle" />,
}));
vi.mock("../../../components/social/SpondsTab", () => ({
  SpondsTab: () => <div className="sponds-tab" />,
}));

vi.mock("../../../hooks/useTickerDetail", () => ({
  useTickerDetail: () => ({ data: undefined }),
}));
vi.mock("../../../hooks/usePeers", () => ({
  usePeers: (_symbol: string, initialPeers?: Array<{ symbol: string; name: string }>) => ({
    data: initialPeers ?? [],
  }),
}));
vi.mock("../../../hooks/useFundamentals", () => ({
  useFundamentals: () => ({ data: undefined }),
  fetchFundamentals: vi.fn(),
}));
vi.mock("../../../hooks/useSavedLists", () => ({
  useSavedLists: () => ({ lists: [] }),
}));
vi.mock("../../../hooks/useMultiplesHistory", () => ({
  // A real query, so the charts tab diverges under restore exactly as the
  // quote query does.
  useMultiplesHistory: () =>
    useQuery({ queryKey: ["multiples-history", "PAM"], queryFn: async () => null }),
  fetchMultiplesHistory: vi.fn(),
}));

import { TickerPageClient } from "./ticker-client";
import type { QuoteResult } from "../../../hooks/usePE10";

/**
 * `isRestoring` is what the browser reports on its first render and the
 * server can never report, so it is the whole difference between the two
 * passes.
 */
function renderTickerPage(pathname: string, isRestoring: boolean): string {
  mockPathname.current = pathname;
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return renderToString(
    <QueryClientProvider client={queryClient}>
      <IsRestoringProvider value={isRestoring}>
        <TickerPageClient initialData={null} />
      </IsRestoringProvider>
    </QueryClientProvider>,
  );
}

const SERVER_PASS = false;
const FIRST_CLIENT_PASS = true;

describe("ticker page hydration safety", () => {
  it("renders identical markup on the server and on the first client pass", () => {
    expect(renderTickerPage("/en/PAM", FIRST_CLIENT_PASS)).toBe(
      renderTickerPage("/en/PAM", SERVER_PASS),
    );
  });

  it("renders identical markup on the fundamentals tab, the URL Sentry sampled", () => {
    expect(renderTickerPage("/en/PAM/fundamentals", FIRST_CLIENT_PASS)).toBe(
      renderTickerPage("/en/PAM/fundamentals", SERVER_PASS),
    );
  });

  it("renders identical markup on the charts tab", () => {
    expect(renderTickerPage("/en/PAM/graficos", FIRST_CLIENT_PASS)).toBe(
      renderTickerPage("/en/PAM/graficos", SERVER_PASS),
    );
  });

  it("shows the metrics skeleton, and no tab bar, until the company arrives", () => {
    const html = renderTickerPage("/en/PAM", FIRST_CLIENT_PASS);
    expect(html).toContain("pe10-loading");
    expect(html).not.toContain("tab-bar");
    expect(html).not.toContain("revisit-banner");
  });
});

/** The smallest quote the page will render a company header for. */
const PAMPA_QUOTE = {
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
} as unknown as QuoteResult;

function renderCompanyPage(initialPeers?: Array<{ symbol: string; name: string }>): string {
  mockPathname.current = "/en/PAM";
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return renderToString(
    <QueryClientProvider client={queryClient}>
      <IsRestoringProvider value={SERVER_PASS}>
        <TickerPageClient initialData={PAMPA_QUOTE} initialPeers={initialPeers} />
      </IsRestoringProvider>
    </QueryClientProvider>,
  );
}

describe("server-rendered company page", () => {
  it("renders the company name as the page's only h1", () => {
    const html = renderCompanyPage();

    expect(html.match(/<h1/g)).toHaveLength(1);
    expect(html).toMatch(/<h1 class="company-header-name">Pampa Energía/);
  });

  it("links to the sector peers the server passed in, so crawlers see them without JavaScript", () => {
    const html = renderCompanyPage([
      { symbol: "YPF", name: "YPF" },
      { symbol: "EDN", name: "Edenor" },
    ]);

    expect(html).toContain('href="/en/YPF"');
    expect(html).toContain('href="/en/EDN"');
  });
});
