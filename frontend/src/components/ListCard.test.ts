import { describe, it, expect } from "vitest";
import { getListCardColumns, computeVisibleRowCount } from "./ListCard";
import { pt } from "../i18n/locales/pt";
import type { TranslationKey } from "../i18n";

const t = (key: TranslationKey) => pt[key];

describe("getListCardColumns", () => {
  it("returns exactly 6 columns", () => {
    const columns = getListCardColumns(10, t);
    expect(columns).toHaveLength(6);
  });

  it("includes the year number in labels that depend on it", () => {
    const columns = getListCardColumns(7, t);
    const labels = columns.map((column) => column.label);

    expect(labels).toContain("P/L7");
    expect(labels).toContain("P/FCL7");
    expect(labels).toContain("PEG7");
    expect(labels).toContain("CAGR L7");
    expect(labels).toContain("ROE7");
    // Dív/PL does not include years
    expect(labels).toContain("Dív/PL");
  });

  it("returns the correct column keys", () => {
    const columns = getListCardColumns(5, t);
    const keys = columns.map((column) => column.key);

    expect(keys).toEqual([
      "pe10",
      "pfcf10",
      "peg",
      "earningsCAGR",
      "debtToEquity",
      "roe",
    ]);
  });

  it("formats values correctly using Brazilian locale", () => {
    const columns = getListCardColumns(10, t);
    const mockData = {
      pe10: 12.5,
      pfcf10: 8.3,
      peg: 1.25,
      earningsCAGR: 15.7,
      debtToEquity: 0.85,
      roe: 22.3,
    } as any;

    const peColumn = columns.find((column) => column.key === "pe10")!;
    expect(peColumn.format(mockData)).toBe("12,5");

    const pfcfColumn = columns.find((column) => column.key === "pfcf10")!;
    expect(pfcfColumn.format(mockData)).toBe("8,3");

    const pegColumn = columns.find((column) => column.key === "peg")!;
    expect(pegColumn.format(mockData)).toBe("1,25");

    const cagrColumn = columns.find((column) => column.key === "earningsCAGR")!;
    expect(cagrColumn.format(mockData)).toBe("15,7%");

    const debtColumn = columns.find((column) => column.key === "debtToEquity")!;
    expect(debtColumn.format(mockData)).toBe("0,85");

    const roeColumn = columns.find((column) => column.key === "roe")!;
    expect(roeColumn.format(mockData)).toBe("22,3%");
  });

  it("returns null for null values", () => {
    const columns = getListCardColumns(10, t);
    const mockData = {
      pe10: null,
      pfcf10: null,
      peg: null,
      earningsCAGR: null,
      debtToEquity: null,
      roe: null,
    } as any;

    for (const column of columns) {
      expect(column.format(mockData)).toBeNull();
    }
  });

  it("extracts numeric values for sorting", () => {
    const columns = getListCardColumns(10, t);
    const mockData = {
      pe10: 12.5,
      pfcf10: 8.3,
      peg: 1.25,
      earningsCAGR: 15.7,
      debtToEquity: 0.85,
      roe: 22.3,
    } as any;

    const peColumn = columns.find((column) => column.key === "pe10")!;
    expect(peColumn.value(mockData)).toBe(12.5);

    const roeColumn = columns.find((column) => column.key === "roe")!;
    expect(roeColumn.value(mockData)).toBe(22.3);
  });

  it("returns null values for sorting when data is null", () => {
    const columns = getListCardColumns(10, t);
    const mockData = {
      pe10: null,
      pfcf10: null,
      peg: null,
      earningsCAGR: null,
      debtToEquity: null,
      roe: null,
    } as any;

    for (const column of columns) {
      expect(column.value(mockData)).toBeNull();
    }
  });

  it("uses English labels when given English translations", async () => {
    const { en } = await import("../i18n/locales/en");
    const tEn = (key: TranslationKey) => en[key];
    const columns = getListCardColumns(10, tEn);
    const labels = columns.map((c) => c.label);

    expect(labels).toContain("P/E10");
    expect(labels).toContain("P/FCF10");
    expect(labels).toContain("D/E");
  });
});

describe("computeVisibleRowCount", () => {
  const rowHeight = 20;
  const totalRows = 11;

  it("returns the minimum when available height is zero", () => {
    expect(computeVisibleRowCount({ availableHeight: 0, rowHeight, totalRows, minRows: 3 })).toBe(3);
  });

  it("never exceeds totalRows", () => {
    expect(computeVisibleRowCount({ availableHeight: 10_000, rowHeight, totalRows, minRows: 3 })).toBe(totalRows);
  });

  it("returns how many whole rows fit in the available height", () => {
    expect(computeVisibleRowCount({ availableHeight: 105, rowHeight, totalRows, minRows: 3 })).toBe(5);
  });

  it("floors partial rows", () => {
    expect(computeVisibleRowCount({ availableHeight: 99, rowHeight, totalRows, minRows: 3 })).toBe(4);
  });

  it("never returns less than minRows even when height is tight", () => {
    expect(computeVisibleRowCount({ availableHeight: 20, rowHeight, totalRows, minRows: 3 })).toBe(3);
  });

  it("caps at totalRows when fewer rows exist than fit", () => {
    expect(computeVisibleRowCount({ availableHeight: 1000, rowHeight, totalRows: 2, minRows: 3 })).toBe(2);
  });

  it("returns totalRows when minRows exceeds totalRows", () => {
    expect(computeVisibleRowCount({ availableHeight: 0, rowHeight, totalRows: 2, minRows: 5 })).toBe(2);
  });

  it("never exceeds maxRows even when more rows fit and exist", () => {
    expect(
      computeVisibleRowCount({ availableHeight: 10_000, rowHeight, totalRows: 20, minRows: 3, maxRows: 9 }),
    ).toBe(9);
  });

  it("returns totalRows when totalRows is below maxRows", () => {
    expect(
      computeVisibleRowCount({ availableHeight: 10_000, rowHeight, totalRows: 4, minRows: 3, maxRows: 9 }),
    ).toBe(4);
  });

  it("respects maxRows even when minRows would exceed it", () => {
    expect(
      computeVisibleRowCount({ availableHeight: 0, rowHeight, totalRows: 20, minRows: 12, maxRows: 9 }),
    ).toBe(9);
  });
});
