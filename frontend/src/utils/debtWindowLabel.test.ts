import { describe, it, expect } from "vitest";
import {
  DEBT_WINDOW_OPTIONS,
  debtCoverageLabel,
  isDebtCoverageIndicator,
  parseDebtWindowYears,
} from "./debtWindowLabel";

describe("debtCoverageLabel", () => {
  it("names the strict window when one is set", () => {
    expect(debtCoverageLabel("Debt / Avg FCF", 5)).toBe("Debt / Avg FCF (5y)");
  });

  it("says the default is loose, up to ten years", () => {
    expect(debtCoverageLabel("Debt / Avg Earnings", null)).toBe(
      "Debt / Avg Earnings (≤10y)",
    );
    expect(debtCoverageLabel("Debt / Avg Earnings", undefined)).toBe(
      "Debt / Avg Earnings (≤10y)",
    );
  });
});

describe("DEBT_WINDOW_OPTIONS", () => {
  it("offers every window from one to fifteen years", () => {
    expect(DEBT_WINDOW_OPTIONS).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]);
  });
});

describe("isDebtCoverageIndicator", () => {
  it("recognises only the two debt-coverage ratios", () => {
    expect(isDebtCoverageIndicator("debt_to_avg_earnings")).toBe(true);
    expect(isDebtCoverageIndicator("debt_to_avg_fcf")).toBe(true);
    expect(isDebtCoverageIndicator("debt_to_equity")).toBe(false);
    expect(isDebtCoverageIndicator("pe10")).toBe(false);
  });
});

describe("parseDebtWindowYears", () => {
  it("maps the empty option to the loose default", () => {
    expect(parseDebtWindowYears("")).toBeNull();
  });

  it("parses an in-range integer", () => {
    expect(parseDebtWindowYears("5")).toBe(5);
    expect(parseDebtWindowYears("15")).toBe(15);
  });

  it("falls back to the loose default for anything out of range", () => {
    expect(parseDebtWindowYears("0")).toBeNull();
    expect(parseDebtWindowYears("16")).toBeNull();
    expect(parseDebtWindowYears("2.5")).toBeNull();
    expect(parseDebtWindowYears("abc")).toBeNull();
  });
});
