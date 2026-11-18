import { describe, it, expect } from "vitest";
import { dateFieldLayout, maskDateDigits, parseLocalizedDate } from "./localizedDate";

describe("dateFieldLayout", () => {
  it.each([
    ["pt", ["day", "month", "year"], "/"],
    ["es", ["day", "month", "year"], "/"],
    ["fr", ["day", "month", "year"], "/"],
    ["it", ["day", "month", "year"], "/"],
    ["en", ["month", "day", "year"], "/"],
    ["de", ["day", "month", "year"], "."],
    ["zh", ["year", "month", "day"], "/"],
  ])("follows %s's numeric date order", (locale, order, separator) => {
    const layout = dateFieldLayout(locale);

    expect(layout.order).toEqual(order);
    expect(layout.separator).toBe(separator);
  });
});

describe("maskDateDigits", () => {
  it("inserts separators as the groups fill in", () => {
    expect(maskDateDigits("1", "pt")).toBe("1");
    expect(maskDateDigits("12", "pt")).toBe("12");
    expect(maskDateDigits("121", "pt")).toBe("12/1");
    expect(maskDateDigits("12112026", "pt")).toBe("12/11/2026");
  });

  it("ignores anything that is not a digit and stops at a full date", () => {
    expect(maskDateDigits("12/11/2026999", "pt")).toBe("12/11/2026");
    expect(maskDateDigits("ab12.11", "de")).toBe("12.11");
  });

  it("groups the year first in Chinese", () => {
    expect(maskDateDigits("20261103", "zh")).toBe("2026/11/03");
  });
});

describe("parseLocalizedDate", () => {
  it("reads day first in Portuguese", () => {
    expect(parseLocalizedDate("12/11/2026", "pt")).toBe("2026-11-12");
  });

  it("reads month first in English", () => {
    expect(parseLocalizedDate("11/12/2026", "en")).toBe("2026-11-12");
  });

  it("reads the German dotted form", () => {
    expect(parseLocalizedDate("12.11.2026", "de")).toBe("2026-11-12");
  });

  it("returns null for an incomplete date", () => {
    expect(parseLocalizedDate("12/11/20", "pt")).toBeNull();
    expect(parseLocalizedDate("", "pt")).toBeNull();
  });

  it("returns null for a date that does not exist", () => {
    expect(parseLocalizedDate("31/02/2026", "pt")).toBeNull();
    expect(parseLocalizedDate("00/10/2026", "pt")).toBeNull();
    expect(parseLocalizedDate("10/13/2026", "pt")).toBeNull();
  });
});
