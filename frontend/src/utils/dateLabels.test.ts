import { describe, it, expect } from "vitest";
import { formatPriceDate } from "./dateLabels";

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
