import { describe, it, expect } from "vitest";
import { brFmt, formatPriceDate, calculateTickInterval } from "./MultiplesChart";

describe("brFmt", () => {
  it("formats with comma as decimal separator", () => {
    const result = brFmt(1234.56);
    expect(result).toContain(",");
    expect(result).toMatch(/1[.]?234,56/);
  });

  it("respects the decimals parameter", () => {
    const zeroDecimals = brFmt(1234.5678, 0);
    expect(zeroDecimals).not.toContain(",");

    const oneDecimal = brFmt(1234.5, 1);
    expect(oneDecimal).toMatch(/1[.]?234,5/);

    const threeDecimals = brFmt(1.123, 3);
    expect(threeDecimals).toMatch(/1,123/);
  });

  it("handles zero", () => {
    const result = brFmt(0);
    expect(result).toMatch(/0,00/);
  });

  it("handles negative numbers", () => {
    const result = brFmt(-42.5);
    expect(result).toContain("42,50");
  });
});

describe("formatPriceDate", () => {
  it('converts "2024-01-31" to "jan/24"', () => {
    expect(formatPriceDate("2024-01-31")).toBe("jan/24");
  });

  it('converts "2015-12-15" to "dez/15"', () => {
    expect(formatPriceDate("2015-12-15")).toBe("dez/15");
  });

  it("handles all 12 months", () => {
    const expected = [
      "jan", "fev", "mar", "abr", "mai", "jun",
      "jul", "ago", "set", "out", "nov", "dez",
    ];
    for (let month = 1; month <= 12; month++) {
      const monthString = String(month).padStart(2, "0");
      const result = formatPriceDate(`2020-${monthString}-01`);
      expect(result).toBe(`${expected[month - 1]}/20`);
    }
  });
});

describe("calculateTickInterval", () => {
  it("returns 1 for 8 or fewer data points", () => {
    expect(calculateTickInterval(1)).toBe(1);
    expect(calculateTickInterval(4)).toBe(1);
    expect(calculateTickInterval(8)).toBe(1);
  });

  it("returns floor(N/8) for larger datasets", () => {
    expect(calculateTickInterval(16)).toBe(2);
    expect(calculateTickInterval(80)).toBe(10);
    expect(calculateTickInterval(100)).toBe(12);
    expect(calculateTickInterval(120)).toBe(15);
  });
});
