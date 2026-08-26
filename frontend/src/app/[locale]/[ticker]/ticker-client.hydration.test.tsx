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
  usePeers: () => ({ data: [] }),
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
