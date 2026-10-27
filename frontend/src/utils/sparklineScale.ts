/**
 * Scale helpers for the card sparklines (MiniChart).
 *
 * A sparkline sits next to its headline number, so its job is to show the
 * shape of the series, not its distance from zero. The value domain is fitted
 * to the data so a one-year window, where ratios move a few percent, uses the
 * card's full height instead of a flat line pinned to the top.
 */

/** Below this share of the series' magnitude, a move is treated as noise. */
const MINIMUM_SPAN_SHARE_OF_MAGNITUDE = 0.01;

/** Span used when every value is zero, so the domain is never a point. */
const ZERO_SERIES_SPAN = 1;

const MAXIMUM_YEAR_TICKS = 8;
const THINNED_YEAR_TICK_TARGET = 6;

interface YearTickedPoint {
  yearTick?: string;
}

export function computeSparklineValueDomain(values: number[]): [number, number] {
  const finiteValues = values.filter(Number.isFinite);
  if (finiteValues.length === 0) return [0, ZERO_SERIES_SPAN];

  const lowest = Math.min(...finiteValues);
  const highest = Math.max(...finiteValues);
  const magnitude = Math.max(Math.abs(lowest), Math.abs(highest));
  const minimumSpan = magnitude > 0
    ? magnitude * MINIMUM_SPAN_SHARE_OF_MAGNITUDE
    : ZERO_SERIES_SPAN;

  if (highest - lowest >= minimumSpan) return [lowest, highest];

  const center = (lowest + highest) / 2;
  return [center - minimumSpan / 2, center + minimumSpan / 2];
}

/** Indexes where a new year starts, thinned out when there are too many. */
export function findYearBoundaryTicks(points: YearTickedPoint[]): number[] {
  const ticks: number[] = [];
  let previousYearTick: string | undefined;
  points.forEach((point, index) => {
    const yearTick = point.yearTick ?? "";
    if (index === 0 || yearTick !== previousYearTick) ticks.push(index);
    previousYearTick = yearTick;
  });

  if (ticks.length <= MAXIMUM_YEAR_TICKS) return ticks;
  const step = Math.ceil(ticks.length / THINNED_YEAR_TICK_TARGET);
  return ticks.filter((_, tickPosition) => tickPosition % step === 0);
}

/**
 * The tick at index 0 lands on the chart's left edge, where Recharts drops it
 * for overflowing. Without a later boundary the axis would render empty and
 * only eat vertical space.
 */
export function hasVisibleYearBoundary(ticks: number[]): boolean {
  return ticks.some((tickIndex) => tickIndex > 0);
}
