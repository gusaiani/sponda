import { describe, it, expect } from "vitest";
import { indicatorKind, isRebasable } from "./indicatorKinds";

describe("indicatorKind", () => {
  it("classifies price as an arbitrary-level currency value", () => {
    expect(indicatorKind("current-price")).toBe("currency-abs-level");
  });

  it("classifies market cap as a meaningful-size currency value", () => {
    expect(indicatorKind("market-cap")).toBe("currency-abs-size");
  });

  it("classifies multiples and leverage ratios as ratios", () => {
    for (const id of ["pe10", "pfcf10", "peg", "pfcfg", "gross-debt-eq", "liab-eq", "current-ratio"]) {
      expect(indicatorKind(id)).toBe("ratio");
    }
  });

  it("classifies CAGRs as percentages", () => {
    expect(indicatorKind("cagr-earnings")).toBe("percent");
    expect(indicatorKind("cagr-fcf")).toBe("percent");
  });

  it("defaults unknown metrics to ratio", () => {
    expect(indicatorKind("something-new")).toBe("ratio");
  });
});

describe("isRebasable", () => {
  it("is true only for currency-denominated absolute values", () => {
    expect(isRebasable("currency-abs-level")).toBe(true);
    expect(isRebasable("currency-abs-size")).toBe(true);
    expect(isRebasable("ratio")).toBe(false);
    expect(isRebasable("percent")).toBe(false);
  });
});
