import { describe, it, expect } from "vitest";
import { formatPriceDate, calculateTickInterval, chartNoticeKeys } from "./MultiplesChart";

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

describe("chartNoticeKeys", () => {
  it("returns no notice when neither approximation was used", () => {
    expect(
      chartNoticeKeys({ currency_warning: false, share_count_approximated: false }),
    ).toEqual([]);
  });

  it("warns when the share count had to stand in for a reported market cap", () => {
    expect(
      chartNoticeKeys({ currency_warning: false, share_count_approximated: true }),
    ).toEqual(["fundamentals.shareCountWarning"]);
  });

  it("warns about FX and the share count independently", () => {
    expect(
      chartNoticeKeys({ currency_warning: true, share_count_approximated: false }),
    ).toEqual(["fundamentals.fxWarning"]);
    expect(
      chartNoticeKeys({ currency_warning: true, share_count_approximated: true }),
    ).toEqual(["fundamentals.fxWarning", "fundamentals.shareCountWarning"]);
  });

  it("treats a response without the flags as carrying no warning", () => {
    expect(chartNoticeKeys({})).toEqual([]);
  });
});
