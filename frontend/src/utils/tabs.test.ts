import { describe, it, expect } from "vitest";
import { resolveTab, buildTabPath, tabSlugForLocale, TAB_LABELS } from "./tabs";

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

describe("TAB_LABELS", () => {
  it("has a label for every tab", () => {
    expect(Object.keys(TAB_LABELS)).toHaveLength(4);
    expect(TAB_LABELS.metrics).toBe("Indicadores");
    expect(TAB_LABELS.fundamentals).toBe("Fundamentos");
    expect(TAB_LABELS.compare).toBe("Comparar");
    expect(TAB_LABELS.charts).toBe("Gráficos");
  });
});
