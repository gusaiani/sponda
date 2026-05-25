import { describe, it, expect } from "vitest";
import {
  rateIndicator,
  rateCompany,
  MIN_INDICATORS_FOR_GRADE,
  METHODOLOGY_VERSION,
} from "./computeRatings";

describe("rateIndicator (lower-better)", () => {
  it.each([
    [0.5, 5],
    [0.49, 5],
    [0.51, 4],
    [1.0, 4],
    [1.49, 3],
    [1.5, 3],
    [1.51, 2],
    [2.5, 2],
    [2.51, 1],
    [10, 1],
  ])("pfcfPeg=%s → tier %s", (value, tier) => {
    expect(rateIndicator("pfcfPeg", value)).toBe(tier);
  });

  it("returns 4 for the bug repro value 0.74 (regression for PFCLG/year-window mismatch)", () => {
    expect(rateIndicator("pfcfPeg", 0.74)).toBe(4);
  });

  it("returns null for null/undefined value", () => {
    expect(rateIndicator("pfcfPeg", null)).toBe(null);
    expect(rateIndicator("pfcfPeg", undefined)).toBe(null);
  });

  it("returns null for unknown indicator", () => {
    expect(rateIndicator("unknownThing", 1)).toBe(null);
  });

  // Negative values for lower-better ratios are an economic signal that the
  // denominator (earnings, FCF, equity) flipped sign — i.e. the underlying
  // business is broken on this dimension. Treating them as "very cheap" (tier
  // 5) is the opposite of the truth. Repro: BLAU3 shows P/FCL10 = -217.4 and
  // was tagged tier 5 instead of tier 1.
  it.each([
    "pe10",
    "pfcf10",
    "peg",
    "pfcfPeg",
    "debtExLeaseToEquity",
    "liabilitiesToEquity",
    "debtToAvgEarnings",
    "debtToAvgFCF",
  ])("rates negative %s as tier 1 (weak), not tier 5", (indicator) => {
    expect(rateIndicator(indicator, -217.4)).toBe(1);
    expect(rateIndicator(indicator, -0.01)).toBe(1);
  });
});

describe("rateIndicator (higher-better)", () => {
  it.each([
    [0.5, 1],
    [0.8, 1],
    [0.81, 2],
    [1.2, 2],
    [1.21, 3],
    [1.6, 3],
    [1.61, 4],
    [2.5, 4],
    [2.51, 5],
    [10, 5],
  ])("currentRatio=%s → tier %s", (value, tier) => {
    expect(rateIndicator("currentRatio", value)).toBe(tier);
  });
});

describe("rateCompany", () => {
  it("rates every indicator passed in and emits null for missing ones", () => {
    const result = rateCompany({
      pe10: 8,
      pfcf10: 10,
      peg: 0.4,
      pfcfPeg: 0.74,
      currentRatio: 2.0,
      debtToAvgEarnings: 1,
      debtToAvgFCF: 1,
      liabilitiesToEquity: 0.3,
      debtExLeaseToEquity: 0.1,
    });
    expect(result.ratings.pe10).toBeGreaterThanOrEqual(1);
    expect(result.ratings.pe10).toBeLessThanOrEqual(5);
    expect(result.ratings.pfcfPeg).toBe(4);
    expect(result.ratings.peg).toBe(5);
    expect(result.methodologyVersion).toBe(METHODOLOGY_VERSION);
  });

  it("returns null overall when fewer than MIN_INDICATORS_FOR_GRADE are rated", () => {
    const result = rateCompany({
      pe10: 8,
      peg: 0.4,
    });
    const ratedCount = Object.values(result.ratings).filter((v) => v !== null).length;
    expect(ratedCount).toBeLessThan(MIN_INDICATORS_FOR_GRADE);
    expect(result.overall).toBe(null);
  });

  it("computes overall as a rounded mean of available tiers", () => {
    // 5 indicators all rated tier 4 → overall 4
    const result = rateCompany({
      pe10: 11,
      pfcf10: 13,
      peg: 0.6,
      pfcfPeg: 0.6,
      currentRatio: 1.5,
    });
    expect(result.ratings.pe10).toBe(4);
    expect(result.ratings.pfcf10).toBe(4);
    expect(result.ratings.peg).toBe(4);
    expect(result.ratings.pfcfPeg).toBe(4);
    expect(result.ratings.currentRatio).toBe(3);
    // mean = (4+4+4+4+3)/5 = 3.8 → round to 4
    expect(result.overall).toBe(4);
  });

  it("falls back from debtExLeaseToEquity to debtToEquity when ex-lease is missing", () => {
    const result = rateCompany({
      debtToEquity: 0.1, // would map to tier 5 under debtExLeaseToEquity cuts [0.2, 0.5, 1.0, 2.0]
    });
    expect(result.ratings.debtExLeaseToEquity).toBe(5);
  });

  it("prefers debtExLeaseToEquity over debtToEquity when both present", () => {
    const result = rateCompany({
      debtExLeaseToEquity: 3.0, // tier 1
      debtToEquity: 0.1, // would be tier 5 — must be ignored
    });
    expect(result.ratings.debtExLeaseToEquity).toBe(1);
  });

  it("emits null for an indicator when its value is null and no fallback applies", () => {
    const result = rateCompany({ pe10: null, peg: 0.5 });
    expect(result.ratings.pe10).toBe(null);
    expect(result.ratings.peg).toBe(5);
  });
});
