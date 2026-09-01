import { describe, it, expect } from "vitest";
import {
  MILLION,
  thresholdUnit,
  toStoredThreshold,
  fromStoredThreshold,
  formatAlertThreshold,
  isThresholdInMillions,
} from "./alertThreshold";

describe("thresholdUnit", () => {
  it("scales market cap thresholds by one million", () => {
    expect(thresholdUnit("market_cap")).toBe(MILLION);
    expect(isThresholdInMillions("market_cap")).toBe(true);
  });

  it("leaves every other indicator unscaled", () => {
    expect(thresholdUnit("current_price")).toBe(1);
    expect(thresholdUnit("pe10")).toBe(1);
    expect(thresholdUnit("debt_to_equity")).toBe(1);
    expect(isThresholdInMillions("pe10")).toBe(false);
  });
});

describe("toStoredThreshold", () => {
  it("multiplies a market cap entered in millions into raw currency units", () => {
    expect(toStoredThreshold("market_cap", "3000")).toBe("3000000000");
  });

  it("keeps fractional millions without floating point noise", () => {
    expect(toStoredThreshold("market_cap", "1.1")).toBe("1100000");
    expect(toStoredThreshold("market_cap", "0.5")).toBe("500000");
  });

  it("passes unscaled indicators through as entered", () => {
    expect(toStoredThreshold("current_price", "30.25")).toBe("30.25");
    expect(toStoredThreshold("pe10", " 12 ")).toBe("12");
  });
});

describe("fromStoredThreshold", () => {
  it("converts a stored market cap back into millions", () => {
    expect(fromStoredThreshold("market_cap", "3000000000.000000")).toBe(3000);
  });

  it("returns the raw number for unscaled indicators", () => {
    expect(fromStoredThreshold("pe10", "12.500000")).toBe(12.5);
  });
});

describe("formatAlertThreshold", () => {
  it("shows market cap in millions with the ticker's currency", () => {
    expect(formatAlertThreshold("market_cap", "3000000000.000000", "PETR4", "pt")).toBe("R$ 3.000M");
    expect(formatAlertThreshold("market_cap", "3000000000.000000", "AAPL", "en")).toBe("$ 3,000M");
  });

  it("keeps up to two decimals of a million and trims trailing zeros", () => {
    expect(formatAlertThreshold("market_cap", "1250000.000000", "PETR4", "pt")).toBe("R$ 1,25M");
    expect(formatAlertThreshold("market_cap", "500000", "AAPL", "en")).toBe("$ 0.5M");
  });

  it("shows prices with two decimals and the ticker's currency", () => {
    expect(formatAlertThreshold("current_price", "30.000000", "PETR4", "pt")).toBe("R$ 30,00");
    expect(formatAlertThreshold("current_price", "150.5", "AAPL", "en")).toBe("$ 150.50");
  });

  it("shows ratios without trailing zeros", () => {
    expect(formatAlertThreshold("pe10", "12.000000", "PETR4", "pt")).toBe("12");
    expect(formatAlertThreshold("debt_to_equity", "1.500000", "AAPL", "en")).toBe("1.5");
  });

  it("returns the raw text when it is not a number", () => {
    expect(formatAlertThreshold("pe10", "abc", "PETR4", "pt")).toBe("abc");
  });
});
