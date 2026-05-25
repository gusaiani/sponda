/**
 * Client-side indicator rating engine. Mirrors backend/quotes/ratings.py but
 * sources its cuts from INDICATOR_CRITERIA so the chip tier always agrees with
 * the tooltip ranges and with the on-screen, window-aware indicator value.
 */
import { INDICATOR_CRITERIA, type Direction } from "./criteria";

export const MIN_INDICATORS_FOR_GRADE = 4;
export const METHODOLOGY_VERSION = "v1";

const RATED_INDICATORS = [
  "pe10",
  "pfcf10",
  "peg",
  "pfcfPeg",
  "debtExLeaseToEquity",
  "liabilitiesToEquity",
  "currentRatio",
  "debtToAvgEarnings",
  "debtToAvgFCF",
] as const;

export type RatedIndicator = (typeof RATED_INDICATORS)[number];

const INDICATOR_VALUE_FALLBACKS: Partial<Record<RatedIndicator, string>> = {
  debtExLeaseToEquity: "debtToEquity",
};

const INDICATOR_WEIGHTS: Record<RatedIndicator, number> = {
  pe10: 1,
  pfcf10: 1,
  peg: 1,
  pfcfPeg: 1,
  debtExLeaseToEquity: 1,
  liabilitiesToEquity: 1,
  currentRatio: 1,
  debtToAvgEarnings: 1,
  debtToAvgFCF: 1,
};

export interface ComputedRatings {
  pe10: number | null;
  pfcf10: number | null;
  peg: number | null;
  pfcfPeg: number | null;
  debtExLeaseToEquity: number | null;
  liabilitiesToEquity: number | null;
  currentRatio: number | null;
  debtToAvgEarnings: number | null;
  debtToAvgFCF: number | null;
}

export interface RateCompanyResult {
  ratings: ComputedRatings;
  overall: number | null;
  methodologyVersion: string;
}

function tierForLowerBetter(value: number, cuts: readonly number[]): number {
  // A negative value on a lower-better ratio (P/E, P/FCF, debt-to-earnings,
  // debt/equity, …) means the denominator flipped sign — earnings, FCF or
  // equity went negative. Rate it as weak rather than letting it slip past
  // the smallest cut and score tier 5.
  if (value < 0) return 1;
  if (value <= cuts[0]) return 5;
  if (value <= cuts[1]) return 4;
  if (value <= cuts[2]) return 3;
  if (value <= cuts[3]) return 2;
  return 1;
}

function tierForHigherBetter(value: number, cuts: readonly number[]): number {
  if (value <= cuts[0]) return 1;
  if (value <= cuts[1]) return 2;
  if (value <= cuts[2]) return 3;
  if (value <= cuts[3]) return 4;
  return 5;
}

export function rateIndicator(
  indicator: string,
  value: number | null | undefined,
): number | null {
  const criteria = INDICATOR_CRITERIA[indicator];
  if (!criteria) return null;
  if (value === null || value === undefined || Number.isNaN(value)) return null;
  const direction: Direction = criteria.direction;
  return direction === "lower"
    ? tierForLowerBetter(value, criteria.cuts)
    : tierForHigherBetter(value, criteria.cuts);
}

export function rateCompany(
  indicatorValues: Partial<Record<string, number | null | undefined>>,
): RateCompanyResult {
  const ratings = {} as ComputedRatings;
  for (const indicator of RATED_INDICATORS) {
    let value = indicatorValues[indicator];
    const fallbackKey = INDICATOR_VALUE_FALLBACKS[indicator];
    if ((value === null || value === undefined) && fallbackKey) {
      value = indicatorValues[fallbackKey];
    }
    ratings[indicator] = rateIndicator(indicator, value ?? null);
  }

  const rated = RATED_INDICATORS
    .map((name) => ({ name, tier: ratings[name] }))
    .filter((entry): entry is { name: RatedIndicator; tier: number } => entry.tier !== null);

  let overall: number | null = null;
  if (rated.length >= MIN_INDICATORS_FOR_GRADE) {
    let weightedSum = 0;
    let totalWeight = 0;
    for (const { name, tier } of rated) {
      const weight = INDICATOR_WEIGHTS[name];
      weightedSum += tier * weight;
      totalWeight += weight;
    }
    if (totalWeight > 0) {
      const mean = weightedSum / totalWeight;
      overall = Math.max(1, Math.min(5, Math.round(mean)));
    }
  }

  return { ratings, overall, methodologyVersion: METHODOLOGY_VERSION };
}
