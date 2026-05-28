/**
 * Derives all year-dependent metrics client-side by slicing the full
 * calculation-details arrays to the requested number of years.
 *
 * This avoids re-fetching from the server when the user moves the slider.
 */
import type { QuoteResult } from "./usePE10";
import { rateCompany } from "../learning/computeRatings";

/* ── CAGR (port of backend/quotes/cagr.py) ── */

interface CAGRResult {
  cagr: number | null;
  method: "endpoint" | "regression" | null;
  error: string | null;
  excludedYears: number[];
}

function computeCAGR(yearlyValues: [number, number][]): CAGRResult {
  if (yearlyValues.length < 2) {
    return { cagr: null, method: null, error: "Dados insuficientes", excludedYears: [] };
  }

  const sorted = [...yearlyValues].sort((a, b) => a[0] - b[0]);
  const [oldestYear, oldestVal] = sorted[0];
  const [newestYear, newestVal] = sorted[sorted.length - 1];
  const nYears = newestYear - oldestYear;

  if (nYears < 1) {
    return { cagr: null, method: null, error: "Dados insuficientes", excludedYears: [] };
  }

  // Try endpoint CAGR
  if (oldestVal > 0 && newestVal > 0) {
    const cagr = (Math.pow(newestVal / oldestVal, 1 / nYears) - 1) * 100;
    return { cagr: Math.round(cagr * 100) / 100, method: "endpoint", error: null, excludedYears: [] };
  }

  // Fallback: log-linear regression on positive years
  const positive = sorted.filter(([, v]) => v > 0);
  const excluded = sorted.filter(([, v]) => v <= 0).map(([y]) => y);

  if (positive.length < 2) {
    return { cagr: null, method: null, error: "Dados insuficientes — anos negativos/zero", excludedYears: excluded };
  }

  const xs = positive.map(([y]) => y);
  const ys = positive.map(([, v]) => Math.log(v));
  const n = xs.length;
  const xMean = xs.reduce((s, x) => s + x, 0) / n;
  const yMean = ys.reduce((s, y) => s + y, 0) / n;

  const numerator = xs.reduce((s, x, i) => s + (x - xMean) * (ys[i] - yMean), 0);
  const denominator = xs.reduce((s, x) => s + (x - xMean) ** 2, 0);

  if (denominator === 0) {
    return { cagr: null, method: null, error: "Dados insuficientes", excludedYears: excluded };
  }

  const slope = numerator / denominator;
  const cagr = (Math.exp(slope) - 1) * 100;
  return { cagr: Math.round(cagr * 100) / 100, method: "regression", error: null, excludedYears: excluded };
}

/**
 * Pick the year window to use for a given company, capped to what the
 * company actually has. Used on the homepage so a young company (e.g.
 * Duolingo with ~4 years of history) still renders its computable
 * indicators and earns a Learn-mode grade badge instead of going blank
 * because the slider is set higher than its data window.
 */
export function effectiveYearsForCompany(
  sliderYears: number,
  maxYearsAvailable: number | null | undefined,
): number {
  if (maxYearsAvailable == null) return sliderYears;
  return Math.max(1, Math.min(sliderYears, maxYearsAvailable));
}

/* ── Trailing-quarters helpers ──
 *
 * The N-year window must cover exactly N×4 quarters of data, not "the
 * top N calendar years". When the most recent fiscal year only has a
 * partial set of quarters reported (e.g. TFCO4 mid-2026 with only Q1
 * 2026 in), the old logic would slice the top N calendar years —
 * (partial 2026 + 2025 + 2024) — sum them, and divide by N. That
 * understated the denominator because year 2026 contributed 1 quarter
 * pretending to be a full year.
 *
 * Correct behaviour: trail back into older years to gather exactly N×4
 * quarters, then divide that adjusted sum by N. The oldest year is
 * synthesised as a partial-tail row so the modal table still adds up
 * to the average it shows.
 */

interface YearAggregateLike {
  year: number;
  ipcaFactor: number;
  quarters: number;
  quarterlyDetail: readonly { end_date: string }[];
}

interface TrailingQuartersResult<Y> {
  /** Sum of adjusted (IPCA-applied) quarterly values over the trailing
   *  N×4 window. Includes pro-rata contribution from a partial oldest
   *  year when the window does not align with a calendar boundary. */
  adjustedSum: number;
  /** adjustedSum / years — the average annual figure used for PE/PFCF. */
  avg: number;
  /** True when the company has at least N×4 quarters of data. */
  hasEnoughData: boolean;
  /** Year-grouped breakdown for display. The oldest entry may be a
   *  synthesised partial-tail year holding only the contributing
   *  quarters. */
  sliced: Y[];
}

function trailingQuartersAverage<Y extends YearAggregateLike>(
  details: readonly Y[],
  years: number,
  getQuarterNominal: (q: Y["quarterlyDetail"][number]) => number,
  buildPartialYear: (
    year: Y,
    takenQuarters: Y["quarterlyDetail"][number][],
    partialNominal: number,
    partialAdjusted: number,
  ) => Y,
): TrailingQuartersResult<Y> {
  const target = years * 4;
  let collected = 0;
  let adjustedSum = 0;
  const sliced: Y[] = [];

  for (const yearData of details) {
    if (collected >= target) break;
    const remaining = target - collected;
    if (yearData.quarters <= remaining) {
      // Full year fits inside the trailing window.
      sliced.push(yearData);
      // Trust the per-year adjusted sum the backend already computed —
      // it's nominal-quarter-sum × ipcaFactor. Recomputing from the
      // quarter list would diverge by a rounding step.
      const yearAdjusted = yearData.quarterlyDetail.reduce(
        (sum, q) => sum + getQuarterNominal(q),
        0,
      ) * yearData.ipcaFactor;
      adjustedSum += yearAdjusted;
      collected += yearData.quarters;
    } else {
      // Partial tail: take the latest `remaining` quarters from this year.
      // quarterlyDetail is sorted ascending by end_date, so slice(-N) is
      // the most-recent N quarters of that year.
      const taken = yearData.quarterlyDetail.slice(-remaining);
      const partialNominal = taken.reduce((sum, q) => sum + getQuarterNominal(q), 0);
      const partialAdjusted = partialNominal * yearData.ipcaFactor;
      adjustedSum += partialAdjusted;
      sliced.push(buildPartialYear(yearData, taken, partialNominal, partialAdjusted));
      collected = target;
    }
  }

  return {
    adjustedSum,
    avg: adjustedSum / years,
    hasEnoughData: collected >= target,
    sliced,
  };
}

/* ── Main derivation ── */

export function deriveForYears(full: QuoteResult, years: number): QuoteResult {
  // Market-cap-based ratios divide by reporting-currency averages, so use
  // the FX-translated market cap from the backend (in reporting currency).
  // Fall back to the raw listing-currency market cap when the backend did
  // not send the translated value — same-currency reporters yield identical
  // numbers either way.
  const marketCapForRatios =
    full.marketCapInReportedCurrency ?? full.marketCap;

  // PE — trailing N×4 quarters
  const earningsTrail = trailingQuartersAverage(
    full.pe10CalculationDetails,
    years,
    (q) => q.net_income,
    (year, taken, partialNominal, partialAdjusted) => ({
      ...year,
      nominalNetIncome: partialNominal,
      adjustedNetIncome: partialAdjusted,
      quarters: taken.length,
      quarterlyDetail: taken,
    }),
  );
  let pe10: number | null = null;
  let avgAdjustedNetIncome: number | null = null;
  let pe10Error: string | null = null;
  if (earningsTrail.hasEnoughData) {
    avgAdjustedNetIncome = earningsTrail.avg;
    if (avgAdjustedNetIncome !== 0 && marketCapForRatios) {
      pe10 = Math.round((marketCapForRatios / avgAdjustedNetIncome) * 100) / 100;
    }
  } else {
    pe10Error = "no_earnings_data";
  }
  const earningsSlice = earningsTrail.hasEnoughData ? earningsTrail.sliced : [];

  // PFCF — trailing N×4 quarters
  const fcfTrail = trailingQuartersAverage(
    full.pfcf10CalculationDetails,
    years,
    (q) => q.fcf,
    (year, taken, partialNominal, partialAdjusted) => ({
      ...year,
      nominalFCF: partialNominal,
      adjustedFCF: partialAdjusted,
      quarters: taken.length,
      quarterlyDetail: taken,
    }),
  );
  let pfcf10: number | null = null;
  let avgAdjustedFCF: number | null = null;
  let pfcf10Error: string | null = null;
  if (fcfTrail.hasEnoughData) {
    avgAdjustedFCF = fcfTrail.avg;
    if (avgAdjustedFCF !== 0 && marketCapForRatios) {
      pfcf10 = Math.round((marketCapForRatios / avgAdjustedFCF) * 100) / 100;
    }
  } else {
    pfcf10Error = "no_cashflow_data";
  }
  const fcfSlice = fcfTrail.hasEnoughData ? fcfTrail.sliced : [];

  // Debt coverage
  let debtToAvgEarnings: number | null = null;
  if (full.totalDebt != null && avgAdjustedNetIncome && avgAdjustedNetIncome > 0) {
    debtToAvgEarnings = Math.round((full.totalDebt / avgAdjustedNetIncome) * 100) / 100;
  }
  let debtToAvgFCF: number | null = null;
  if (full.totalDebt != null && avgAdjustedFCF && avgAdjustedFCF > 0) {
    debtToAvgFCF = Math.round((full.totalDebt / avgAdjustedFCF) * 100) / 100;
  }

  // CAGR (earnings) — partial calendar years (most-recent year not yet
  // closed, or the synthesised partial-tail year at the oldest edge of the
  // trailing window) cannot be compared against full years on the same
  // axis, because their adjusted total is a fraction of a year's
  // earnings. Filter them out so the growth rate doesn't collapse to a
  // bogus number like "-76% YoY" when the latest year only has Q1
  // reported. A TTM-endpoint rewrite is a follow-up.
  const earningsCAGRInput: [number, number][] = earningsSlice
    .filter((y) => y.quarters >= 4)
    .map((y) => [y.year, y.adjustedNetIncome]);
  const earningsCagr = computeCAGR(earningsCAGRInput);

  // PEG
  let peg: number | null = null;
  let pegError: string | null = null;
  if (pe10 === null) {
    pegError = "pe_unavailable";
  } else if (pe10 < 0) {
    pegError = "pe_negative";
  } else if (earningsCagr.cagr === null) {
    pegError = earningsCagr.error;
  } else if (earningsCagr.cagr <= 0) {
    pegError = "negative_growth";
  } else {
    peg = Math.round((pe10 / earningsCagr.cagr) * 100) / 100;
  }

  // CAGR (FCF) — same partial-year filter as earnings, see above.
  const fcfCAGRInput: [number, number][] = fcfSlice
    .filter((y) => y.quarters >= 4)
    .map((y) => [y.year, y.adjustedFCF]);
  const fcfCagr = computeCAGR(fcfCAGRInput);

  // PFCLG
  let pfcfPeg: number | null = null;
  let pfcfPegError: string | null = null;
  if (pfcf10 === null) {
    pfcfPegError = "pfcf_unavailable";
  } else if (pfcf10 < 0) {
    pfcfPegError = "pfcf_negative";
  } else if (fcfCagr.cagr === null) {
    pfcfPegError = fcfCagr.error;
  } else if (fcfCagr.cagr <= 0) {
    pfcfPegError = "negative_growth";
  } else {
    pfcfPeg = Math.round((pfcf10 / fcfCagr.cagr) * 100) / 100;
  }

  // ROE = avg adjusted net income / stockholders equity
  let roe: number | null = null;
  if (avgAdjustedNetIncome && avgAdjustedNetIncome > 0 && full.stockholdersEquity && full.stockholdersEquity > 0) {
    roe = Math.round((avgAdjustedNetIncome / full.stockholdersEquity) * 10000) / 100;
  }

  // P/VPA = market cap / stockholders equity
  let priceToBook: number | null = null;
  if (full.marketCap && full.stockholdersEquity && full.stockholdersEquity > 0) {
    priceToBook = Math.round((full.marketCap / full.stockholdersEquity) * 100) / 100;
  }

  // Learning Mode ratings, computed against the *derived* (window-aware)
  // indicator values so the chip tier always matches the number shown on the
  // card. Leverage/liquidity indicators are not year-dependent and pass
  // through unchanged.
  const derivedRating = rateCompany({
    pe10,
    pfcf10,
    peg,
    pfcfPeg,
    debtToEquity: full.debtToEquity,
    debtExLeaseToEquity: full.debtExLeaseToEquity,
    liabilitiesToEquity: full.liabilitiesToEquity,
    currentRatio: full.currentRatio,
    debtToAvgEarnings,
    debtToAvgFCF,
  });
  const ratings = {
    pe10: derivedRating.ratings.pe10,
    pfcf10: derivedRating.ratings.pfcf10,
    peg: derivedRating.ratings.peg,
    pfcfPeg: derivedRating.ratings.pfcfPeg,
    debtToEquity: null,
    debtExLeaseToEquity: derivedRating.ratings.debtExLeaseToEquity,
    liabilitiesToEquity: derivedRating.ratings.liabilitiesToEquity,
    currentRatio: derivedRating.ratings.currentRatio,
    debtToAvgEarnings: derivedRating.ratings.debtToAvgEarnings,
    debtToAvgFCF: derivedRating.ratings.debtToAvgFCF,
    overall: derivedRating.overall,
    methodologyVersion: derivedRating.methodologyVersion,
  };

  return {
    ...full,
    // PE
    pe10,
    avgAdjustedNetIncome,
    // Divisor displayed in the modal — always N. The detail list may
    // be N+1 rows long when the trailing window slices into an extra
    // calendar year, but the average is over N years either way.
    pe10YearsOfData: earningsTrail.hasEnoughData ? years : 0,
    pe10Label: `PE${years}`,
    pe10Error,
    pe10CalculationDetails: earningsSlice,
    // PFCF
    pfcf10,
    avgAdjustedFCF,
    pfcf10YearsOfData: fcfTrail.hasEnoughData ? years : 0,
    pfcf10Label: `PFCF${years}`,
    pfcf10Error,
    pfcf10CalculationDetails: fcfSlice,
    // Debt coverage
    debtToAvgEarnings,
    debtToAvgFCF,
    // PEG
    peg,
    earningsCAGR: earningsCagr.cagr,
    pegError,
    earningsCAGRMethod: earningsCagr.method,
    earningsCAGRExcludedYears: earningsCagr.excludedYears,
    // PFCLG
    pfcfPeg,
    fcfCAGR: fcfCagr.cagr,
    pfcfPegError,
    fcfCAGRMethod: fcfCagr.method,
    fcfCAGRExcludedYears: fcfCagr.excludedYears,
    // Profitability
    roe,
    priceToBook,
    // Window-aware ratings (overrides the backend's max-years snapshot so the
    // chip tier matches the displayed indicator value).
    ratings,
  };
}
