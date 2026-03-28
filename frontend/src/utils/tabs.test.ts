import { describe, it, expect } from "vitest";
import { resolveTab, buildTabPath, TAB_LABELS } from "./tabs";

describe("resolveTab", () => {
  it("returns metrics for the root ticker path", () => {
    expect(resolveTab("/PETR4")).toBe("metrics");
  });

  it("returns charts for /graficos", () => {
    expect(resolveTab("/PETR4/graficos")).toBe("charts");
  });

  it("returns fundamentals for /fundamentos", () => {
    expect(resolveTab("/VALE3/fundamentos")).toBe("fundamentals");
  });

  it("returns compare for /comparar", () => {
    expect(resolveTab("/ITUB4/comparar")).toBe("compare");
  });

  it("returns metrics for unknown paths", () => {
    expect(resolveTab("/PETR4/unknown")).toBe("metrics");
  });

  it("returns metrics for empty pathname", () => {
    expect(resolveTab("/")).toBe("metrics");
  });
});

describe("buildTabPath", () => {
  it("builds root path for metrics", () => {
    expect(buildTabPath("PETR4", "metrics")).toBe("/PETR4");
  });

  it("builds /graficos for charts", () => {
    expect(buildTabPath("PETR4", "charts")).toBe("/PETR4/graficos");
  });

  it("builds /fundamentos for fundamentals", () => {
    expect(buildTabPath("VALE3", "fundamentals")).toBe("/VALE3/fundamentos");
  });

  it("builds /comparar for compare", () => {
    expect(buildTabPath("ITUB4", "compare")).toBe("/ITUB4/comparar");
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
