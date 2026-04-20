import { describe, it, expect, vi } from "vitest";
import {
  localizeLabel,
  ptLabel,
  formatNumber,
  formatLargeNumber,
  formatQuarterLabel,
  currencyCode,
  localToday,
} from "./format";

describe("currencyCode", () => {
  it("returns BRL for Brazilian tickers", () => {
    expect(currencyCode("COGN3")).toBe("BRL");
    expect(currencyCode("PETR4")).toBe("BRL");
    expect(currencyCode("SANB11")).toBe("BRL");
  });

  it("returns USD for US tickers", () => {
    expect(currencyCode("AAPL")).toBe("USD");
    expect(currencyCode("MSFT")).toBe("USD");
    expect(currencyCode("SCCO")).toBe("USD");
  });
});

describe("localizeLabel", () => {
  it("converts PE10 to P/L10 in Portuguese", () => {
    expect(localizeLabel("PE10", "pt")).toBe("P/L10");
  });

  it("converts PFCF10 to P/FCL10 in Portuguese", () => {
    expect(localizeLabel("PFCF10", "pt")).toBe("P/FCL10");
  });

  it("keeps PE10 as PE10 in English", () => {
    expect(localizeLabel("PE10", "en")).toBe("PE10");
  });

  it("keeps PFCF10 as PFCF10 in English", () => {
    expect(localizeLabel("PFCF10", "en")).toBe("PFCF10");
  });

  it("leaves other strings unchanged in both locales", () => {
    expect(localizeLabel("CAGR", "pt")).toBe("CAGR");
    expect(localizeLabel("CAGR", "en")).toBe("CAGR");
  });
});

describe("ptLabel (deprecated)", () => {
  it("converts PE10 to P/L10", () => {
    expect(ptLabel("PE10")).toBe("P/L10");
  });

  it("converts PFCF7 to P/FCL7", () => {
    expect(ptLabel("PFCF7")).toBe("P/FCL7");
  });
});

describe("formatNumber", () => {
  it("uses comma as decimal separator in Portuguese", () => {
    expect(formatNumber(1.5, 2, "pt")).toBe("1,50");
    expect(formatNumber(3.14159, 3, "pt")).toBe("3,142");
  });

  it("uses period as decimal separator in English", () => {
    expect(formatNumber(1.5, 2, "en")).toBe("1.50");
    expect(formatNumber(3.14159, 3, "en")).toBe("3.142");
  });

  it("uses comma as decimal separator in Spanish", () => {
    expect(formatNumber(1.5, 2, "es")).toBe("1,50");
  });

  it("uses comma as decimal separator in German", () => {
    expect(formatNumber(1.5, 2, "de")).toBe("1,50");
  });

  it("uses comma as decimal separator in French", () => {
    expect(formatNumber(1.5, 2, "fr")).toMatch(/^1,50$/);
  });

  it("uses comma as decimal separator in Italian", () => {
    expect(formatNumber(1.5, 2, "it")).toBe("1,50");
  });

  it("uses period as decimal separator in Chinese", () => {
    expect(formatNumber(1.5, 2, "zh")).toBe("1.50");
  });

  it("formats thousands with locale conventions (en)", () => {
    expect(formatNumber(1234.56, 2, "en")).toBe("1,234.56");
  });

  it("formats thousands with locale conventions (pt)", () => {
    expect(formatNumber(1234.56, 2, "pt")).toBe("1.234,56");
  });

  it("formats thousands with locale conventions (de)", () => {
    expect(formatNumber(1234.56, 2, "de")).toBe("1.234,56");
  });

  it("respects the digits parameter", () => {
    expect(formatNumber(1.5, 0, "pt")).toBe("2");
    expect(formatNumber(1.5, 0, "en")).toBe("2");
  });

  it("replaces hyphen-minus with en-dash for negative numbers", () => {
    const ptResult = formatNumber(-5, 0, "pt");
    expect(ptResult).not.toContain("-");
    expect(ptResult).toBe("\u20135");

    const enResult = formatNumber(-5, 0, "en");
    expect(enResult).not.toContain("-");
    expect(enResult).toBe("\u20135");
  });

  it("handles zero", () => {
    expect(formatNumber(0, 0, "pt")).toBe("0");
    expect(formatNumber(0, 2, "pt")).toBe("0,00");
    expect(formatNumber(0, 2, "en")).toBe("0.00");
  });
});

describe("formatLargeNumber", () => {
  it("formats billions with B suffix in Portuguese", () => {
    const result = formatLargeNumber(2_500_000_000, "", "pt");
    expect(result).toMatch(/^R\$ .+B$/);
    expect(result).toContain("2,50");
  });

  it("formats billions with B suffix in English for US ticker", () => {
    const result = formatLargeNumber(2_500_000_000, "AAPL", "en");
    expect(result).toMatch(/^\$ .+B$/);
    expect(result).toContain("2.50");
  });

  it("formats millions with M suffix in Portuguese", () => {
    const result = formatLargeNumber(350_000_000, "", "pt");
    expect(result).toMatch(/^R\$ .+M$/);
    expect(result).toContain("350,00");
  });

  it("formats millions with M suffix in English", () => {
    const result = formatLargeNumber(350_000_000, "AAPL", "en");
    expect(result).toMatch(/^\$ .+M$/);
    expect(result).toContain("350.00");
  });

  it("formats thousands with K suffix in Portuguese", () => {
    const result = formatLargeNumber(42_000, "", "pt");
    expect(result).toMatch(/^R\$ .+K$/);
    expect(result).toContain("42,0");
  });

  it("formats thousands with K suffix in English", () => {
    const result = formatLargeNumber(42_000, "AAPL", "en");
    expect(result).toMatch(/^\$ .+K$/);
    expect(result).toContain("42.0");
  });

  it("formats small numbers without suffix in Portuguese", () => {
    expect(formatLargeNumber(500, "", "pt")).toBe("R$ 500");
  });

  it("formats small numbers without suffix in English", () => {
    expect(formatLargeNumber(500, "AAPL", "en")).toBe("$ 500");
  });

  it("handles negative values in billions with en-dash", () => {
    const result = formatLargeNumber(-1_000_000_000, "", "pt");
    expect(result).toMatch(/^R\$ .+B$/);
    expect(result).toContain("\u2013");
  });

  it("handles negative values in millions with en-dash", () => {
    const result = formatLargeNumber(-50_000_000, "", "pt");
    expect(result).toMatch(/^R\$ .+M$/);
    expect(result).toContain("\u2013");
  });

  it("uses R$ prefix for Brazilian tickers regardless of locale", () => {
    expect(formatLargeNumber(1_000_000, "PETR4", "en")).toMatch(/^R\$ /);
    expect(formatLargeNumber(1_000_000, "PETR4", "pt")).toMatch(/^R\$ /);
  });

  it("uses $ prefix for US tickers regardless of locale", () => {
    expect(formatLargeNumber(1_000_000, "AAPL", "en")).toMatch(/^\$ /);
    expect(formatLargeNumber(1_000_000, "AAPL", "pt")).toMatch(/^\$ /);
  });
});

describe("formatQuarterLabel", () => {
  it("returns 1T2024 for 2024-03-31", () => {
    expect(formatQuarterLabel("2024-03-31")).toBe("1T2024");
  });

  it("returns 2T2024 for 2024-06-30", () => {
    expect(formatQuarterLabel("2024-06-30")).toBe("2T2024");
  });

  it("returns 3T2024 for 2024-09-30", () => {
    expect(formatQuarterLabel("2024-09-30")).toBe("3T2024");
  });

  it("returns 4T2024 for 2024-12-31", () => {
    expect(formatQuarterLabel("2024-12-31")).toBe("4T2024");
  });

  it("returns 1T2023 for 2023-01-15", () => {
    expect(formatQuarterLabel("2023-01-15")).toBe("1T2023");
  });
});

describe("localToday", () => {
  it("returns the current local date as YYYY-MM-DD", () => {
    const result = localToday();
    expect(result).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  it("uses local timezone, not UTC", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-04-16T02:00:00Z"));

    const result = localToday();
    const expected = new Date();
    const expectedDate = `${expected.getFullYear()}-${String(expected.getMonth() + 1).padStart(2, "0")}-${String(expected.getDate()).padStart(2, "0")}`;
    expect(result).toBe(expectedDate);

    vi.useRealTimers();
  });

  it("pads single-digit months and days with leading zeros", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 0, 5, 12, 0, 0));
    expect(localToday()).toBe("2026-01-05");
    vi.useRealTimers();
  });
});
