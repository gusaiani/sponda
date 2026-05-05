/**
 * Frontend mirror of the default thresholds from `backend/quotes/ratings.py`.
 *
 * Keeping a small copy here lets the indicator tooltips render the criteria
 * for each tier without an extra round-trip. When the backend adds per-sector
 * overrides this file should grow a fetch (or be replaced by a config
 * endpoint) — for v1 the defaults are the only profile in use.
 */
import { formatNumber } from "../utils/format";

export type Direction = "lower" | "higher";

export interface IndicatorCriteria {
  direction: Direction;
  cuts: [number, number, number, number];
}

export const INDICATOR_CRITERIA: Record<string, IndicatorCriteria> = {
  pe10: { direction: "lower", cuts: [10, 15, 20, 30] },
  pfcf10: { direction: "lower", cuts: [12, 18, 25, 35] },
  peg: { direction: "lower", cuts: [0.5, 1.0, 1.5, 2.5] },
  pfcfPeg: { direction: "lower", cuts: [0.5, 1.0, 1.5, 2.5] },
  debtToEquity: { direction: "lower", cuts: [0.3, 0.7, 1.5, 3.0] },
  debtExLeaseToEquity: { direction: "lower", cuts: [0.2, 0.5, 1.0, 2.0] },
  liabilitiesToEquity: { direction: "lower", cuts: [0.5, 1.5, 3.0, 5.0] },
  currentRatio: { direction: "higher", cuts: [0.8, 1.2, 1.6, 2.5] },
  debtToAvgEarnings: { direction: "lower", cuts: [2, 4, 6, 10] },
  debtToAvgFCF: { direction: "lower", cuts: [3, 5, 8, 12] },
};

function digitsFor(value: number): number {
  if (Number.isInteger(value)) return 0;
  return value < 1 ? 2 : 1;
}

function fmt(value: number, locale: string): string {
  return formatNumber(value, digitsFor(value), locale);
}

export interface TierRange {
  tier: 1 | 2 | 3 | 4 | 5;
  range: string;
}

export function tierRanges(indicator: string, locale: string): TierRange[] {
  const criteria = INDICATOR_CRITERIA[indicator];
  if (!criteria) return [];
  const [c1, c2, c3, c4] = criteria.cuts;
  const lowerToTopRanges: TierRange[] = [
    { tier: 5, range: `≤ ${fmt(c1, locale)}` },
    { tier: 4, range: `${fmt(c1, locale)} – ${fmt(c2, locale)}` },
    { tier: 3, range: `${fmt(c2, locale)} – ${fmt(c3, locale)}` },
    { tier: 2, range: `${fmt(c3, locale)} – ${fmt(c4, locale)}` },
    { tier: 1, range: `> ${fmt(c4, locale)}` },
  ];
  if (criteria.direction === "lower") return lowerToTopRanges;
  return [
    { tier: 1, range: `≤ ${fmt(c1, locale)}` },
    { tier: 2, range: `${fmt(c1, locale)} – ${fmt(c2, locale)}` },
    { tier: 3, range: `${fmt(c2, locale)} – ${fmt(c3, locale)}` },
    { tier: 4, range: `${fmt(c3, locale)} – ${fmt(c4, locale)}` },
    { tier: 5, range: `> ${fmt(c4, locale)}` },
  ].reverse() as TierRange[];
}
