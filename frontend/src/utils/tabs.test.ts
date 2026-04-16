import { describe, it, expect } from "vitest";
import { resolveTab, buildTabPath, tabSlugForLocale, TAB_LABELS, buildOwnerSwapUrl } from "./tabs";

describe("resolveTab", () => {
  it("returns metrics for the root ticker path", () => {
    expect(resolveTab("/en/PETR4")).toBe("metrics");
  });

  it("resolves English tab slugs", () => {
    expect(resolveTab("/en/PETR4/charts")).toBe("charts");
    expect(resolveTab("/en/PETR4/fundamentals")).toBe("fundamentals");
    expect(resolveTab("/en/PETR4/compare")).toBe("compare");
  });

  it("resolves Portuguese tab slugs", () => {
    expect(resolveTab("/pt/PETR4/graficos")).toBe("charts");
    expect(resolveTab("/pt/VALE3/fundamentos")).toBe("fundamentals");
    expect(resolveTab("/pt/ITUB4/comparar")).toBe("compare");
  });

  it("resolves slugs regardless of locale prefix", () => {
    // Both PT and EN slugs resolve correctly no matter what
    expect(resolveTab("/en/PETR4/fundamentos")).toBe("fundamentals");
    expect(resolveTab("/pt/PETR4/fundamentals")).toBe("fundamentals");
  });

  it("returns metrics for unknown paths", () => {
    expect(resolveTab("/en/PETR4/unknown")).toBe("metrics");
  });

  it("returns metrics for empty pathname", () => {
    expect(resolveTab("/")).toBe("metrics");
  });

  it("handles paths without locale prefix (backward compat)", () => {
    expect(resolveTab("/PETR4/graficos")).toBe("charts");
    expect(resolveTab("/PETR4/fundamentals")).toBe("fundamentals");
    expect(resolveTab("/PETR4")).toBe("metrics");
  });
});

describe("buildTabPath", () => {
  it("builds locale-prefixed path for metrics (no tab suffix)", () => {
    expect(buildTabPath("en", "PETR4", "metrics")).toBe("/en/PETR4");
    expect(buildTabPath("pt", "PETR4", "metrics")).toBe("/pt/PETR4");
  });

  it("builds English tab paths", () => {
    expect(buildTabPath("en", "PETR4", "charts")).toBe("/en/PETR4/charts");
    expect(buildTabPath("en", "VALE3", "fundamentals")).toBe("/en/VALE3/fundamentals");
    expect(buildTabPath("en", "ITUB4", "compare")).toBe("/en/ITUB4/compare");
  });

  it("builds Portuguese tab paths", () => {
    expect(buildTabPath("pt", "PETR4", "charts")).toBe("/pt/PETR4/graficos");
    expect(buildTabPath("pt", "VALE3", "fundamentals")).toBe("/pt/VALE3/fundamentos");
    expect(buildTabPath("pt", "ITUB4", "compare")).toBe("/pt/ITUB4/comparar");
  });
});

describe("tabSlugForLocale", () => {
  it("returns Portuguese slugs for pt", () => {
    expect(tabSlugForLocale("pt", "charts")).toBe("graficos");
    expect(tabSlugForLocale("pt", "fundamentals")).toBe("fundamentos");
    expect(tabSlugForLocale("pt", "compare")).toBe("comparar");
  });

  it("returns English slugs for en", () => {
    expect(tabSlugForLocale("en", "charts")).toBe("charts");
    expect(tabSlugForLocale("en", "fundamentals")).toBe("fundamentals");
    expect(tabSlugForLocale("en", "compare")).toBe("compare");
  });

  it("returns empty string for metrics", () => {
    expect(tabSlugForLocale("en", "metrics")).toBe("");
    expect(tabSlugForLocale("pt", "metrics")).toBe("");
  });
});

describe("buildOwnerSwapUrl", () => {
  it("targets the new owner's compare tab in the given locale", () => {
    const result = buildOwnerSwapUrl("pt", "VALE3", ["PETR4"], new URLSearchParams());
    expect(result).toBe("/pt/VALE3/comparar?with=PETR4");
  });

  it("encodes the new extras as a comma-separated 'with' param", () => {
    const result = buildOwnerSwapUrl(
      "en",
      "AAPL",
      ["MSFT", "GOOG", "AMZN"],
      new URLSearchParams(),
    );
    expect(result).toBe("/en/AAPL/compare?with=MSFT%2CGOOG%2CAMZN");
  });

  it("preserves listId and years from the source URL", () => {
    const source = new URLSearchParams("listId=42&years=7");
    const result = buildOwnerSwapUrl("pt", "ITUB4", ["BBDC4"], source);
    expect(result).toContain("/pt/ITUB4/comparar");
    expect(result).toContain("listId=42");
    expect(result).toContain("years=7");
    expect(result).toContain("with=BBDC4");
  });

  it("omits the with param when there are no extras", () => {
    const result = buildOwnerSwapUrl("en", "AAPL", [], new URLSearchParams());
    expect(result).toBe("/en/AAPL/compare");
  });

  it("ignores irrelevant source params", () => {
    const source = new URLSearchParams("foo=bar&listId=1");
    const result = buildOwnerSwapUrl("en", "AAPL", ["MSFT"], source);
    expect(result).not.toContain("foo");
    expect(result).toContain("listId=1");
  });
});

describe("TAB_LABELS", () => {
  it("has a label for every tab", () => {
    expect(Object.keys(TAB_LABELS)).toHaveLength(4);
    expect(TAB_LABELS.metrics).toBe("Indicadores");
    expect(TAB_LABELS.fundamentals).toBe("Fundamentos");
    expect(TAB_LABELS.compare).toBe("Comparar");
    expect(TAB_LABELS.charts).toBe("Gráficos");
  });
});
