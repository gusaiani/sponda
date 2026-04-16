import { describe, it, expect } from "vitest";
import { buildScreenerQuery, ScreenerFilters } from "./useScreener";

function makeFilters(overrides: Partial<ScreenerFilters> = {}): ScreenerFilters {
  return {
    bounds: {},
    sort: "ticker",
    limit: 50,
    offset: 0,
    ...overrides,
  };
}

describe("buildScreenerQuery", () => {
  it("emits only sort/limit/offset when no bounds are set", () => {
    const query = buildScreenerQuery(makeFilters());
    const params = new URLSearchParams(query);
    expect(params.get("sort")).toBe("ticker");
    expect(params.get("limit")).toBe("50");
    expect(params.get("offset")).toBe("0");
    expect(params.get("pe10_min")).toBeNull();
  });

  it("emits indicator_min and indicator_max when both are set", () => {
    const query = buildScreenerQuery(
      makeFilters({ bounds: { pe10: { min: "5", max: "15" } } }),
    );
    const params = new URLSearchParams(query);
    expect(params.get("pe10_min")).toBe("5");
    expect(params.get("pe10_max")).toBe("15");
  });

  it("skips empty-string bounds", () => {
    const query = buildScreenerQuery(
      makeFilters({ bounds: { pe10: { min: "", max: "10" } } }),
    );
    const params = new URLSearchParams(query);
    expect(params.get("pe10_min")).toBeNull();
    expect(params.get("pe10_max")).toBe("10");
  });

  it("encodes multiple indicator bounds independently", () => {
    const query = buildScreenerQuery(
      makeFilters({
        bounds: {
          pe10: { max: "10" },
          debt_to_equity: { max: "1.5" },
          market_cap: { min: "1000000000" },
        },
      }),
    );
    const params = new URLSearchParams(query);
    expect(params.get("pe10_max")).toBe("10");
    expect(params.get("debt_to_equity_max")).toBe("1.5");
    expect(params.get("market_cap_min")).toBe("1000000000");
  });

  it("propagates the sort direction prefix", () => {
    const query = buildScreenerQuery(makeFilters({ sort: "-pe10" }));
    const params = new URLSearchParams(query);
    expect(params.get("sort")).toBe("-pe10");
  });
});
