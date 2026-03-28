import { describe, it, expect } from "vitest";
import { getListCardColumns } from "./ListCard";

describe("getListCardColumns", () => {
  it("returns exactly 6 columns", () => {
    const columns = getListCardColumns(10);
    expect(columns).toHaveLength(6);
  });

  it("includes the year number in labels that depend on it", () => {
    const columns = getListCardColumns(7);
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
    const columns = getListCardColumns(5);
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
    const columns = getListCardColumns(10);
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
    const columns = getListCardColumns(10);
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
    const columns = getListCardColumns(10);
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
    const columns = getListCardColumns(10);
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
});
