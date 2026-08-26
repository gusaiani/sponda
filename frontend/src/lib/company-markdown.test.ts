import { describe, it, expect, vi, afterEach } from "vitest";
import {
  buildCompanyMarkdownModel,
  fetchCompanyMarkdownData,
  renderCompanyMarkdown,
  escapeTableCell,
  type CompanyMarkdownData,
  type CompanySnapshot,
} from "./company-markdown";
import { SUPPORTED_LOCALES } from "./i18n-config";

const PETROBRAS_SNAPSHOT: CompanySnapshot = {
  symbol: "PETR4",
  name: "Petrobras",
  sector: "Oil",
  country: "BR",
  reported_currency: "BRL",
  market_cap: 400_000_000_000,
  current_price: 35.75,
  computed_at: "2026-08-26T12:00:00+00:00",
  pe10: 6.5,
  pe1: 4.2,
  pe15: 7.1,
  pe_years_available: 15,
  pfcf10: 8,
  peg: 0.5,
  pfcf_peg: 0.7,
  debt_to_equity: 1.2,
  debt_ex_lease_to_equity: 1,
  liabilities_to_equity: 2,
  current_ratio: 1.4,
  debt_to_avg_earnings: 3,
  debt_to_avg_fcf: 4.5,
};

const PETROBRAS: CompanyMarkdownData = {
  snapshot: PETROBRAS_SNAPSHOT,
  analysis: null,
  peers: [],
  fundamentals: null,
};

function render(overrides: Partial<CompanyMarkdownData> = {}, locale = "en", tab = "metrics") {
  return renderCompanyMarkdown(
    buildCompanyMarkdownModel({
      ticker: "PETR4",
      locale: locale as never,
      tab: tab as never,
      data: { ...PETROBRAS, ...overrides },
    }),
  );
}

describe("renderCompanyMarkdown · metrics", () => {
  it("opens with an h1 naming the company and the ticker", () => {
    expect(render().split("\n")[0]).toBe("# Petrobras (PETR4)");
  });

  it("states the sector and the reporting currency up front", () => {
    const output = render();
    expect(output).toContain("Oil");
    expect(output).toContain("BRL");
  });

  it("prints the headline indicators as a table", () => {
    const output = render();
    expect(output).toContain("| 6.50 |");
    expect(output).toContain("| 8.00 |");
    expect(output).toContain("| 0.50 |");
  });

  it("says which P/E window the company can honestly fill", () => {
    expect(render()).toContain("15");
  });

  it("links back to the HTML page", () => {
    expect(render()).toContain("https://sponda.capital/en/PETR4");
  });

  it("links to the other tabs as markdown, not HTML", () => {
    const output = render();
    expect(output).toContain("https://sponda.capital/en/PETR4/charts.md");
    expect(output).toContain("https://sponda.capital/en/PETR4/fundamentals.md");
    expect(output).toContain("https://sponda.capital/en/PETR4/compare.md");
  });

  it("points at the glossary rather than repeating it on 23k pages", () => {
    expect(render()).toContain("https://sponda.capital/en/screener.md");
  });

  it("prints the share price at full precision, not rounded to the unit", () => {
    // formatLargeNumber drops the decimals below 1000, which turns a 35.75
    // share price into 36. A price is not a market cap.
    expect(render()).toContain("35.75");
    expect(render()).not.toMatch(/\|\s*R\$ 36\s*\|/);
  });

  it("still abbreviates the market cap", () => {
    expect(render()).toContain("400.00B");
  });

  it("writes a negative number with an ASCII minus", () => {
    // formatNumber swaps the hyphen for an en dash for the HTML pages. A
    // model that does not recognise U+2013 as a minus reads a loss as a gain.
    const output = render({
      snapshot: { ...PETROBRAS_SNAPSHOT, peg: -0.5, debt_to_equity: -1.2 },
    });
    expect(output).toContain("-0.50");
    expect(output).not.toContain("\u2013");
  });

  it("dates itself from computed_at", () => {
    expect(render()).toContain("2026-08-26");
  });
});

describe("missing values", () => {
  const sparse: Partial<CompanyMarkdownData> = {
    snapshot: {
      ...PETROBRAS_SNAPSHOT,
      pe10: null,
      peg: null,
      current_price: null,
      market_cap: null,
      computed_at: null,
    },
  };

  it("never emits NaN, null or undefined", () => {
    const output = render(sparse);
    for (const poison of ["NaN", "null", "undefined", "Infinity"]) {
      expect(output, poison).not.toContain(poison);
    }
  });

  it("omits an indicator row rather than printing an empty one", () => {
    const output = render(sparse);
    expect(output).not.toMatch(/\|\s*P\/E10[^|]*\|\s*\|/);
  });

  it("still renders a heading and a link for a company with no numbers", () => {
    const output = render(sparse);
    expect(output.startsWith("# Petrobras (PETR4)")).toBe(true);
    expect(output).toContain("https://sponda.capital/en/PETR4");
  });
});

describe("analysis", () => {
  it("includes the stored analysis markdown when there is one", () => {
    const output = render({ analysis: { content: "## Tese\n\nTexto.", generatedAt: "2026-08-01T00:00:00Z" } });
    expect(output).toContain("## Tese");
    expect(output).toContain("Texto.");
  });

  it("omits the whole section when there is none", () => {
    expect(render({ analysis: null })).not.toContain("## Tese");
  });

  it("says the analysis is in Portuguese when the page is not", () => {
    const withAnalysis = { analysis: { content: "Texto.", generatedAt: "2026-08-01T00:00:00Z" } };
    expect(render(withAnalysis, "de")).toMatch(/portug/i);
    expect(render(withAnalysis, "pt")).not.toMatch(/O texto abaixo/i);
  });

  it("demotes analysis headings so they never outrank the page title", () => {
    const output = render({ analysis: { content: "# Top\n\nx", generatedAt: null } });
    expect(output).not.toMatch(/^# Top$/m);
    expect(output).toMatch(/^### Top$/m);
  });
});

describe("tabs", () => {
  it("charts renders the P/E term structure", () => {
    const output = render({}, "en", "charts");
    expect(output).toContain("P/E1");
    expect(output).toContain("P/E15");
    expect(output).toContain("| 4.20 |");
  });

  it("charts marks windows the company cannot fill as unavailable, not zero", () => {
    const output = render(
      { snapshot: { ...PETROBRAS_SNAPSHOT, pe15: null, pe_years_available: 10 } },
      "en",
      "charts",
    );
    expect(output).not.toContain("| 0.00 |");
  });

  it("compare renders the peer table", () => {
    const output = render(
      {
        peers: [
          { symbol: "VALE3", name: "Vale", sector: "Mining", pe10: 4.1, pfcf10: 5.2, peg: 0.3, market_cap: 300_000_000_000 },
        ],
      },
      "en",
      "compare",
    );
    expect(output).toContain("VALE3");
    expect(output).toContain("Vale");
    expect(output).toContain("4.10");
  });

  it("compare says so plainly when there are no peers", () => {
    const output = render({ peers: [] }, "en", "compare");
    expect(output).toContain("# Petrobras (PETR4)");
    expect(output).not.toContain("| VALE3 |");
  });

  it("fundamentals renders the annual table when one is available", () => {
    const output = render(
      {
        fundamentals: {
          years: [
            { year: 2025, revenue: 500_000_000_000, revenueAdjusted: 520_000_000_000, netIncome: 40_000_000_000, netIncomeAdjusted: 41_000_000_000, fcf: 30_000_000_000, fcfAdjusted: 31_000_000_000, totalDebt: 100_000_000_000, stockholdersEquity: 300_000_000_000, quarters: 4 },
          ],
          listingCurrency: "BRL",
          reportedCurrency: "BRL",
          omitted: ["annualPriceMultiples", "dividends"],
        },
      },
      "en",
      "fundamentals",
    );
    expect(output).toContain("2025");
    // Inflation-adjusted figures win over nominal ones: 520B, not 500B.
    expect(output).toMatch(/520/);
    expect(output).not.toMatch(/\b500\.00B/);
  });

  it("fundamentals names the columns it cannot fill instead of hiding them", () => {
    const output = render(
      {
        fundamentals: {
          years: [],
          listingCurrency: "BRL",
          reportedCurrency: "BRL",
          omitted: ["annualPriceMultiples", "dividends"],
        },
      },
      "en",
      "fundamentals",
    );
    expect(output).toMatch(/dividend/i);
  });
});

describe("locales", () => {
  it("renders in every supported locale without a missing key", () => {
    for (const locale of SUPPORTED_LOCALES) {
      const output = render({}, locale);
      expect(output, locale).toContain("# Petrobras (PETR4)");
      expect(output, locale).toContain(`https://sponda.capital/${locale}/PETR4`);
      expect(output, locale).not.toContain("undefined");
    }
  });

  it("uses each locale's own tab slug in the cross-links", () => {
    expect(render({}, "pt")).toContain("/pt/PETR4/graficos.md");
    expect(render({}, "de")).toContain("/de/PETR4/fundamentaldaten.md");
  });

  it("formats numbers for the locale", () => {
    expect(render({}, "pt")).toContain("6,50");
    expect(render({}, "en")).toContain("6.50");
  });
});

describe("fetchCompanyMarkdownData", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("fetches a company page in one request", async () => {
    // Two round trips per page, one of them un-cacheable because it 404s for
    // most companies, is what the consolidated endpoint exists to avoid.
    const fetchMock = vi.fn(async (input: unknown) => {
      void input;
      return new Response("{}", { status: 200 });
    });
    vi.stubGlobal("fetch", fetchMock);

    await fetchCompanyMarkdownData("PETR4", "metrics");

    expect(fetchMock.mock.calls).toHaveLength(1);
    expect(String(fetchMock.mock.calls[0][0])).toContain("analysis=1");
  });

  it("asks for the annual table only on the fundamentals tab", async () => {
    const fetchMock = vi.fn(async (input: unknown) => {
      void input;
      return new Response("{}", { status: 200 });
    });
    vi.stubGlobal("fetch", fetchMock);

    await fetchCompanyMarkdownData("PETR4", "charts");
    expect(String(fetchMock.mock.calls[0][0])).not.toContain("fundamentals=1");

    fetchMock.mockClear();
    await fetchCompanyMarkdownData("PETR4", "fundamentals");
    expect(String(fetchMock.mock.calls[0][0])).toContain("fundamentals=1");
  });

  it("never calls the quota-gated quote endpoint", async () => {
    const fetchMock = vi.fn(async (input: unknown) => {
      void input;
      return new Response("{}", { status: 200 });
    });
    vi.stubGlobal("fetch", fetchMock);

    await fetchCompanyMarkdownData("PETR4", "metrics");

    for (const call of fetchMock.mock.calls) {
      const url = String(call[0]);
      expect(url, url).not.toMatch(/\/api\/quote\/[^/]+\/$/);
      expect(url, url).not.toContain("/fundamentals/");
      expect(url, url).not.toContain("/multiples-history/");
    }
  });

  it("reads indicators from the snapshot endpoint", async () => {
    const fetchMock = vi.fn(async (input: unknown) => {
      void input;
      return new Response("{}", { status: 200 });
    });
    vi.stubGlobal("fetch", fetchMock);

    await fetchCompanyMarkdownData("PETR4", "metrics");

    const urls = fetchMock.mock.calls.map((call) => String(call[0]));
    expect(urls.some((url) => url.includes("/api/tickers/PETR4/indicators/"))).toBe(true);
  });

  it("returns a null snapshot for an unknown ticker instead of throwing", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("", { status: 404 })));
    const data = await fetchCompanyMarkdownData("NOPE99", "metrics");
    expect(data.snapshot).toBeNull();
  });

  it("renders a company whose analysis is null", async () => {
    vi.stubGlobal("fetch", vi.fn(async () =>
      new Response(JSON.stringify({ ...PETROBRAS_SNAPSHOT, analysis: null }), { status: 200 }),
    ));
    const data = await fetchCompanyMarkdownData("PETR4", "metrics");
    expect(data.snapshot?.symbol).toBe("PETR4");
    expect(data.analysis).toBeNull();
  });

  it("picks up an analysis carried on the snapshot payload", async () => {
    vi.stubGlobal("fetch", vi.fn(async () =>
      new Response(JSON.stringify({
        ...PETROBRAS_SNAPSHOT,
        analysis: { content: "## Tese", generatedAt: "2026-08-01T00:00:00Z" },
      }), { status: 200 }),
    ));
    const data = await fetchCompanyMarkdownData("PETR4", "metrics");
    expect(data.analysis?.content).toBe("## Tese");
  });
});

describe("table safety", () => {
  it("escapes a pipe so one bad company name cannot corrupt the table", () => {
    const output = renderCompanyMarkdown(
      buildCompanyMarkdownModel({
        ticker: "WEIRD",
        locale: "en" as never,
        tab: "compare" as never,
        data: {
          ...PETROBRAS,
          peers: [{ symbol: "X1", name: "Pipe | Co", pe10: 1 }],
        },
      }),
    );
    expect(output).toContain("Pipe \\| Co");
  });

  it("flattens a newline inside a cell", () => {
    expect(escapeTableCell("two\nlines")).toBe("two lines");
  });
});
