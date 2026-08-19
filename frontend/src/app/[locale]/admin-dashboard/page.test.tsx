// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render as renderBare, screen, cleanup, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

/**
 * The page fetches through react-query, so it needs a client. Retries are off
 * and gcTime is zero so a failing request fails once, immediately, and nothing
 * leaks between tests.
 */
function render(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return renderBare(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

const authState = {
  isAuthenticated: true,
  isSuperuser: true,
  isLoading: false,
};

vi.mock("../../../hooks/useAuth", () => ({
  useAuth: () => authState,
}));

vi.mock("../../../i18n", () => ({
  useTranslation: () => ({ t: (key: string) => key, locale: "pt" }),
}));

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

import AdminDashboardPage from "./page";

function makeMcpQueryStats(overrides: Record<string, unknown> = {}) {
  return {
    top_indicators: [
      { indicator: "pe10", screen_count: 30 },
      { indicator: "current_ratio", screen_count: 4 },
    ],
    top_countries: [{ country: "BR", screen_count: 12 }],
    top_sectors: [{ sector: "Oil", screen_count: 5 }],
    zero_result_screens: { count: 3, total_screens: 40 },
    failed_symbol_lookups: [{ symbol: "NOPE9", request_count: 2 }],
    ...overrides,
  };
}

function makeMcpStats(overrides: Record<string, unknown> = {}) {
  return {
    queries: makeMcpQueryStats(),
    periods: {
      day: { total_calls: 12, tool_calls: 9, unique_clients: 3, failed_calls: 1, rate_limited_calls: 0 },
      week: { total_calls: 40, tool_calls: 31, unique_clients: 7, failed_calls: 2, rate_limited_calls: 1 },
      month: { total_calls: 90, tool_calls: 70, unique_clients: 11, failed_calls: 4, rate_limited_calls: 1 },
      year: { total_calls: 90, tool_calls: 70, unique_clients: 11, failed_calls: 4, rate_limited_calls: 1 },
      all_time: { total_calls: 90, tool_calls: 70, unique_clients: 11, failed_calls: 4, rate_limited_calls: 1 },
    },
    top_tools: [
      { tool_name: "screen_companies", call_count: 45 },
      { tool_name: "get_company", call_count: 20 },
    ],
    top_clients: [{ client_name: "claude-code", connection_count: 6 }],
    daily_calls: [
      { date: "2026-08-14", call_count: 5 },
      { date: "2026-08-15", call_count: 12 },
    ],
    ...overrides,
  };
}

function makeDashboardData(overrides: Record<string, unknown> = {}) {
  return {
    users: [],
    page_views: {
      day: { total_views: 100, unique_visitors: 20, authenticated_views: 5, anonymous_views: 95 },
    },
    top_pages: [],
    top_tickers: {},
    signup_stats: { total: 3, day: 0, week: 1, month: 2, year: 3 },
    mcp: makeMcpStats(),
    favorites_count: 0,
    saved_lists_count: 0,
    ...overrides,
  };
}

function mockDashboardResponse(data: Record<string, unknown>) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, json: async () => data }),
  );
}

async function findMcpSection(): Promise<HTMLElement> {
  return screen.findByRole("region", { name: "Servidor MCP" });
}

describe("AdminDashboardPage — MCP usage section", () => {
  beforeEach(() => {
    authState.isAuthenticated = true;
    authState.isSuperuser = true;
    authState.isLoading = false;
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("shows MCP calls in the last 24h as an overview card", async () => {
    mockDashboardResponse(makeDashboardData());
    render(<AdminDashboardPage />);

    const card = await screen.findByText("Chamadas MCP (24h)");
    expect(within(card.parentElement as HTMLElement).getByText("12")).toBeTruthy();
  });

  it("renders one row per period with calls, tool calls and unique clients", async () => {
    mockDashboardResponse(makeDashboardData());
    render(<AdminDashboardPage />);

    const section = await findMcpSection();
    const weekRow = within(section).getByText("7 dias").closest("tr") as HTMLElement;
    const cells = within(weekRow).getAllByRole("cell").map((cell) => cell.textContent);
    expect(cells).toEqual(["7 dias", "40", "31", "7", "2", "1"]);
  });

  it("ranks the most-called tools", async () => {
    mockDashboardResponse(makeDashboardData());
    render(<AdminDashboardPage />);

    const section = await findMcpSection();
    expect(within(section).getByText("screen_companies")).toBeTruthy();
    expect(within(section).getByText("get_company")).toBeTruthy();
  });

  it("lists the clients that connected", async () => {
    mockDashboardResponse(makeDashboardData());
    render(<AdminDashboardPage />);

    const section = await findMcpSection();
    expect(within(section).getByText("claude-code")).toBeTruthy();
  });

  it("says so plainly when nothing has been recorded yet", async () => {
    mockDashboardResponse(
      makeDashboardData({ mcp: makeMcpStats({ top_tools: [], top_clients: [] }) }),
    );
    render(<AdminDashboardPage />);

    const section = await findMcpSection();
    expect(within(section).getByText("Nenhuma chamada registrada")).toBeTruthy();
    expect(within(section).getByText("Nenhum cliente identificado")).toBeTruthy();
  });

  it("ranks the indicators, countries and sectors screens actually used", async () => {
    mockDashboardResponse(makeDashboardData());
    render(<AdminDashboardPage />);

    const section = await findMcpSection();
    expect(within(section).getByText("pe10")).toBeTruthy();
    expect(within(section).getByText("current_ratio")).toBeTruthy();
    expect(within(section).getByText("BR")).toBeTruthy();
    expect(within(section).getByText("Oil")).toBeTruthy();
  });

  it("shows the zero-result screen rate", async () => {
    mockDashboardResponse(makeDashboardData());
    render(<AdminDashboardPage />);

    const section = await findMcpSection();
    expect(
      within(section).getByText("Screens sem resultado: 3 de 40"),
    ).toBeTruthy();
  });

  it("lists the symbols callers asked for that could not be served", async () => {
    mockDashboardResponse(makeDashboardData());
    render(<AdminDashboardPage />);

    const section = await findMcpSection();
    const symbolRow = within(section).getByText("NOPE9").closest("tr") as HTMLElement;
    expect(within(symbolRow).getByText("2")).toBeTruthy();
  });

  it("says so plainly when no queries were mined yet", async () => {
    mockDashboardResponse(
      makeDashboardData({
        mcp: makeMcpStats({
          queries: makeMcpQueryStats({
            top_indicators: [],
            top_countries: [],
            top_sectors: [],
            zero_result_screens: { count: 0, total_screens: 0 },
            failed_symbol_lookups: [],
          }),
        }),
      }),
    );
    render(<AdminDashboardPage />);

    const section = await findMcpSection();
    expect(within(section).getAllByText("Nenhum registro").length).toBe(4);
  });

  it("does not crash on a backend without query stats", async () => {
    mockDashboardResponse(
      makeDashboardData({ mcp: makeMcpStats({ queries: undefined }) }),
    );
    render(<AdminDashboardPage />);

    const section = await findMcpSection();
    expect(within(section).getByText("screen_companies")).toBeTruthy();
    expect(within(section).queryByText("Consultas (30 dias)")).toBeNull();
  });

  it("does not crash when the API omits the mcp section", async () => {
    const { mcp: _omitted, ...withoutMcp } = makeDashboardData();
    mockDashboardResponse(withoutMcp);
    render(<AdminDashboardPage />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /Painel de Administração/i })).toBeTruthy();
    });
    expect(screen.queryByRole("region", { name: "Servidor MCP" })).toBeNull();
  });
});
