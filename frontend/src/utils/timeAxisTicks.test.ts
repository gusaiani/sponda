import { describe, it, expect } from "vitest";
import { buildTimeAxisTicks, formatTimeAxisTick } from "./timeAxisTicks";

const MAX_TICKS = 12;

function utc(isoDate: string): number {
  return Date.parse(`${isoDate}T00:00:00Z`);
}

/** One timestamp per weekday between two dates, like a daily price series. */
function tradingDays(fromIsoDate: string, toIsoDate: string): number[] {
  const days: number[] = [];
  for (let timestamp = utc(fromIsoDate); timestamp <= utc(toIsoDate); timestamp += 86_400_000) {
    const weekday = new Date(timestamp).getUTCDay();
    if (weekday !== 0 && weekday !== 6) days.push(timestamp);
  }
  return days;
}

describe("buildTimeAxisTicks", () => {
  it("ticks every month when the window covers less than a year", () => {
    const { ticks, granularity } = buildTimeAxisTicks(tradingDays("2026-01-02", "2026-10-27"), MAX_TICKS);
    expect(granularity).toBe("month");
    expect(ticks.map((timestamp) => new Date(timestamp).getUTCMonth())).toEqual(
      [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    );
  });

  it("places each month tick on that month's first point", () => {
    const { ticks } = buildTimeAxisTicks(tradingDays("2026-01-02", "2026-03-10"), MAX_TICKS);
    expect(ticks).toEqual([utc("2026-01-02"), utc("2026-02-02"), utc("2026-03-02")]);
  });

  it("thins month ticks on a two-year window instead of crowding the axis", () => {
    const { ticks, granularity } = buildTimeAxisTicks(tradingDays("2025-01-02", "2026-10-27"), MAX_TICKS);
    expect(granularity).toBe("month");
    expect(ticks.length).toBeLessThanOrEqual(MAX_TICKS);
    expect(ticks[0]).toBe(utc("2025-01-02"));
  });

  it("ticks every year on long windows", () => {
    const { ticks, granularity } = buildTimeAxisTicks(tradingDays("2020-01-02", "2026-10-27"), MAX_TICKS);
    expect(granularity).toBe("year");
    expect(ticks.map((timestamp) => new Date(timestamp).getUTCFullYear())).toEqual(
      [2020, 2021, 2022, 2023, 2024, 2025, 2026],
    );
  });

  it("thins year ticks on a fifteen-year window", () => {
    const { ticks } = buildTimeAxisTicks(tradingDays("2012-01-02", "2026-10-27"), MAX_TICKS);
    expect(ticks.length).toBeLessThanOrEqual(MAX_TICKS);
  });

  it("returns no ticks for an empty series", () => {
    expect(buildTimeAxisTicks([], MAX_TICKS).ticks).toEqual([]);
  });
});

describe("formatTimeAxisTick", () => {
  it("labels a year tick with its two-digit year", () => {
    expect(formatTimeAxisTick(utc("2026-01-02"), "year", "pt")).toBe("26");
  });

  it("labels a month tick with the month and year, in the reader's language", () => {
    expect(formatTimeAxisTick(utc("2026-02-02"), "month", "pt")).toBe("fev/26");
    expect(formatTimeAxisTick(utc("2026-02-02"), "month", "en")).toBe("Feb/26");
  });
});
