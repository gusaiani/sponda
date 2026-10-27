import { describe, it, expect } from "vitest";
import {
  computeSparklineValueDomain,
  findYearBoundaryTicks,
  hasVisibleYearBoundary,
} from "./sparklineScale";

function yearPoints(yearTicks: string[]) {
  return yearTicks.map((yearTick, index) => ({ label: String(index), value: index, yearTick }));
}

describe("computeSparklineValueDomain", () => {
  it("fits the domain to the data instead of anchoring it at zero", () => {
    expect(computeSparklineValueDomain([1.91, 2.4, 2.1])).toEqual([1.91, 2.4]);
  });

  it("covers negative values so series crossing zero stay in frame", () => {
    expect(computeSparklineValueDomain([-3, 5, 1])).toEqual([-3, 5]);
  });

  it("centers a flat series instead of collapsing the domain to a point", () => {
    const [lower, upper] = computeSparklineValueDomain([0.49, 0.49, 0.49]);
    expect(lower).toBeLessThan(0.49);
    expect(upper).toBeGreaterThan(0.49);
    expect((lower + upper) / 2).toBeCloseTo(0.49);
  });

  it("does not blow rounding noise up to the full chart height", () => {
    const [lower, upper] = computeSparklineValueDomain([100, 100.0001]);
    const visibleShare = 0.0001 / (upper - lower);
    expect(visibleShare).toBeLessThan(0.01);
  });

  it("still uses the full height for a small but real move", () => {
    expect(computeSparklineValueDomain([0.47, 0.49])).toEqual([0.47, 0.49]);
  });

  it("gives an all-zero series a non-empty domain", () => {
    const [lower, upper] = computeSparklineValueDomain([0, 0]);
    expect(lower).toBeLessThan(0);
    expect(upper).toBeGreaterThan(0);
  });

  it("ignores non-finite values", () => {
    expect(computeSparklineValueDomain([2, Number.NaN, 4, Infinity])).toEqual([2, 4]);
  });
});

describe("findYearBoundaryTicks", () => {
  it("marks the first index of every year", () => {
    expect(findYearBoundaryTicks(yearPoints(["24", "24", "25", "25", "26"]))).toEqual([0, 2, 4]);
  });

  it("thins out crowded year ticks", () => {
    const fifteenYears = Array.from({ length: 15 }, (_, year) => String(11 + year));
    const ticks = findYearBoundaryTicks(yearPoints(fifteenYears));
    expect(ticks.length).toBeLessThanOrEqual(8);
    expect(ticks[0]).toBe(0);
  });
});

describe("hasVisibleYearBoundary", () => {
  it("is false when the whole series sits inside one year", () => {
    expect(hasVisibleYearBoundary([0])).toBe(false);
  });

  it("is true once a year starts after the first point", () => {
    expect(hasVisibleYearBoundary([0, 3])).toBe(true);
  });
});
