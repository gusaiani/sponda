import { describe, it, expect } from "vitest";
import {
  labelToTimestamp,
  convertSeries,
  buildAlignedDataset,
  hasMixedCurrencies,
  type NamedSeries,
} from "./normalizeSeries";
import type { DataPoint } from "../components/MiniChart";

function series(ticker: string, currency: string, points: DataPoint[]): NamedSeries {
  return { ticker, name: ticker, color: "#000", currency, points };
}

describe("labelToTimestamp", () => {
  it("anchors year-only labels to year end so they sort with dated labels", () => {
    expect(labelToTimestamp("2023") < labelToTimestamp("2024")).toBe(true);
    expect(labelToTimestamp("2024-01-31") < labelToTimestamp("2024")).toBe(true);
  });
});

describe("convertSeries", () => {
  const points: DataPoint[] = [
    { label: "2024-01-02", value: 10 },
    { label: "2024-01-03", value: 20 },
  ];

  it("returns points unchanged when the FX path is empty (identity)", () => {
    expect(convertSeries(points, [])).toEqual(points);
  });

  it("multiplies each point by the step-sampled rate", () => {
    const out = convertSeries(points, [
      { date: "2024-01-02", rate: 0.2 },
      { date: "2024-01-03", rate: 0.25 },
    ]);
    expect(out[0].value).toBeCloseTo(2);
    expect(out[1].value).toBeCloseTo(5);
  });

  it("falls back to the first rate for dates before the first anchor", () => {
    const out = convertSeries([{ label: "2023-06-01", value: 10 }], [
      { date: "2024-01-02", rate: 0.2 },
    ]);
    expect(out[0].value).toBeCloseTo(2);
  });
});

describe("buildAlignedDataset", () => {
  it("returns empty when no series have points", () => {
    expect(buildAlignedDataset([series("A", "BRL", [])])).toEqual({ rows: [], tickers: [] });
  });

  it("merges series onto one axis starting at the latest common start", () => {
    const a = series("A", "BRL", [
      { label: "2022", value: 1 },
      { label: "2023", value: 2 },
      { label: "2024", value: 3 },
    ]);
    const b = series("B", "BRL", [
      { label: "2023", value: 10 },
      { label: "2024", value: 20 },
    ]);
    const { rows, tickers } = buildAlignedDataset([a, b]);
    expect(tickers).toEqual(["A", "B"]);
    // Axis starts at 2023 (B's start), so the 2022 point is dropped.
    expect(rows).toHaveLength(2);
    expect(rows[0].A).toBe(2);
    expect(rows[0].B).toBe(10);
    expect(rows[1].A).toBe(3);
    expect(rows[1].B).toBe(20);
  });

  it("rebases every series to 100 at the common origin", () => {
    const a = series("A", "BRL", [
      { label: "2023", value: 2 },
      { label: "2024", value: 3 },
    ]);
    const b = series("B", "USD", [
      { label: "2023", value: 10 },
      { label: "2024", value: 20 },
    ]);
    const { rows } = buildAlignedDataset([a, b], { rebase: true });
    expect(rows[0].A).toBeCloseTo(100);
    expect(rows[0].B).toBeCloseTo(100);
    expect(rows[1].A).toBeCloseTo(150);
    expect(rows[1].B).toBeCloseTo(200);
  });

  it("carries a series forward with its last value between sparse points", () => {
    const daily = series("A", "BRL", [
      { label: "2024-01-01", value: 5 },
      { label: "2024-01-03", value: 7 },
    ]);
    const sparse = series("B", "BRL", [
      { label: "2024-01-01", value: 100 },
      { label: "2024-01-03", value: 100 },
    ]);
    const { rows } = buildAlignedDataset([daily, sparse]);
    // Row for 2024-01-03 should carry B forward (it has a point there too).
    const last = rows[rows.length - 1];
    expect(last.A).toBe(7);
    expect(last.B).toBe(100);
  });
});

describe("hasMixedCurrencies", () => {
  it("detects when series span more than one currency", () => {
    expect(hasMixedCurrencies([series("A", "BRL", []), series("B", "USD", [])])).toBe(true);
    expect(hasMixedCurrencies([series("A", "BRL", []), series("B", "BRL", [])])).toBe(false);
  });
});
