import { inferPeriodsPerYear, trailingQuartersAverage } from "../hooks/deriveForYears";
import type { FundamentalsYear } from "../hooks/useFundamentals";
import type { TranslationKey } from "../i18n";

/* Trailing-window ratios per fiscal year: the P/L, P/FCL and debt coverage
 * columns of the Fundamentos table, and the debt coverage columns of the
 * Comparar table, which show the same numbers for each company's most
 * recent year. One implementation, so the two tables cannot disagree. */

/** Why a trailing ratio has no value, when the table can say so:
 *  - insufficient_history: fewer than N × periodsPerYear filings end at
 *    or before this year, so no honest N-year window exists.
 *  - negative_average: the window average is not positive, so debt
 *    divided by it is not a repayment horizon (debt coverage only).
 *  A ratio can also be blank for a reason the row already shows (no
 *  market cap or no debt figure that year); those carry no reason. */
export type RatioUnavailableReason = "insufficient_history" | "negative_average";

export interface TrailingRatioUnavailableReasons {
  pe: RatioUnavailableReason | null;
  pfcf: RatioUnavailableReason | null;
  debtToEarnings: RatioUnavailableReason | null;
  debtToFcf: RatioUnavailableReason | null;
}

export interface TrailingRatios {
  pe: number | null;
  pfcf: number | null;
  debtToEarnings: number | null;
  debtToFcf: number | null;
  unavailableReasons: TrailingRatioUnavailableReasons;
}

export const NO_UNAVAILABLE_REASONS: TrailingRatioUnavailableReasons = {
  pe: null,
  pfcf: null,
  debtToEarnings: null,
  debtToFcf: null,
};

export const NULL_TRAILING_RATIOS: TrailingRatios = {
  pe: null,
  pfcf: null,
  debtToEarnings: null,
  debtToFcf: null,
  unavailableReasons: NO_UNAVAILABLE_REASONS,
};

/** One ratio cell: its value, or why there is none. */
interface RatioOutcome {
  value: number | null;
  unavailableReason: RatioUnavailableReason | null;
}

function available(value: number): RatioOutcome {
  return { value: Math.round(value * 100) / 100, unavailableReason: null };
}

function unavailable(reason: RatioUnavailableReason | null): RatioOutcome {
  return { value: null, unavailableReason: reason };
}

interface EarningsQuarterDetail {
  end_date: string;
  net_income: number;
}

interface CashFlowQuarterDetail {
  end_date: string;
  fcf: number;
}

interface YearDetail<QuarterDetail> {
  year: number;
  ipcaFactor: number;
  quarters: number;
  quarterlyDetail: QuarterDetail[];
}

/** The slice of the quote payload the ratio columns need, satisfied
 *  structurally by QuoteResult. */
export interface TrailingRatioSource {
  pe10CalculationDetails: YearDetail<EarningsQuarterDetail>[];
  pfcf10CalculationDetails: YearDetail<CashFlowQuarterDetail>[];
  pe10PeriodsPerYear?: number;
  pfcf10PeriodsPerYear?: number;
}

function anchoredTrailingAverage<QuarterDetail extends { end_date: string }>(
  details: YearDetail<QuarterDetail>[],
  anchorYear: number,
  windowYears: number,
  periodsPerYear: number,
  getPeriodNominal: (quarter: QuarterDetail) => number,
): number | null {
  const anchoredDescending = details
    .filter((yearDetail) => yearDetail.year <= anchorYear)
    .sort((a, b) => b.year - a.year);
  const trail = trailingQuartersAverage(
    anchoredDescending,
    windowYears,
    periodsPerYear,
    getPeriodNominal,
    (yearDetail, taken) => ({ ...yearDetail, quarters: taken.length, quarterlyDetail: taken }),
  );
  return trail.hasEnoughData ? trail.avg : null;
}

/**
 * P/L{N}, P/FCL{N}, Debt/Earnings{N}, and Debt/FCL{N} per historical
 * year, computed with the same trailing-window math the Indicadores tab
 * uses: each year's window is exactly N × periodsPerYear filings
 * ending at that year's last filed period. A year without enough
 * trailing history gets null (rendered as a dash) instead of a
 * silently-shrunk average. Both the numerators (market cap, debt) and
 * the averaged figures are in today's purchasing power, which is
 * equivalent to comparing both in that year's money.
 *
 * Debt coverage mirrors the Metrics-tab indicator (deriveForYears):
 * it only exists when the trailing average is positive. Dividing debt
 * by negative earnings is meaningless as a repayment horizon.
 */
export function computeTrailingRatios(
  data: FundamentalsYear[],
  source: TrailingRatioSource | null,
  windowYears: number,
): Map<number, TrailingRatios> {
  const result = new Map<number, TrailingRatios>();
  if (source === null) {
    // The quote payload has not loaded: nothing is computable yet, and
    // "insufficient history" would be a false explanation.
    for (const row of data) result.set(row.year, NULL_TRAILING_RATIOS);
    return result;
  }
  const earningsDetails = source.pe10CalculationDetails;
  const cashFlowDetails = source.pfcf10CalculationDetails;
  const earningsPeriodsPerYear =
    source.pe10PeriodsPerYear ?? inferPeriodsPerYear(earningsDetails);
  const cashFlowPeriodsPerYear =
    source.pfcf10PeriodsPerYear ?? inferPeriodsPerYear(cashFlowDetails);

  for (const row of data) {
    const marketCap = row.marketCapAdjusted ?? row.marketCap;
    const debt = row.debtExLeaseAdjusted ?? row.debtExLease;
    if (marketCap === null && debt === null) {
      result.set(row.year, NULL_TRAILING_RATIOS);
      continue;
    }

    const averageEarnings = anchoredTrailingAverage(
      earningsDetails, row.year, windowYears, earningsPeriodsPerYear,
      (quarter) => quarter.net_income,
    );
    const averageFcf = anchoredTrailingAverage(
      cashFlowDetails, row.year, windowYears, cashFlowPeriodsPerYear,
      (quarter) => quarter.fcf,
    );

    const priceRatio = (average: number | null): RatioOutcome => {
      if (average === null) return unavailable("insufficient_history");
      if (marketCap === null || average === 0) return unavailable(null);
      return available(marketCap / average);
    };
    const debtCoverageRatio = (average: number | null): RatioOutcome => {
      if (average === null) return unavailable("insufficient_history");
      if (debt === null) return unavailable(null);
      if (average <= 0) return unavailable("negative_average");
      return available(debt / average);
    };

    const pe = priceRatio(averageEarnings);
    const pfcf = priceRatio(averageFcf);
    const debtToEarnings = debtCoverageRatio(averageEarnings);
    const debtToFcf = debtCoverageRatio(averageFcf);

    result.set(row.year, {
      pe: pe.value,
      pfcf: pfcf.value,
      debtToEarnings: debtToEarnings.value,
      debtToFcf: debtToFcf.value,
      unavailableReasons: {
        pe: pe.unavailableReason,
        pfcf: pfcf.unavailableReason,
        debtToEarnings: debtToEarnings.unavailableReason,
        debtToFcf: debtToFcf.unavailableReason,
      },
    });
  }

  return result;
}

export type TrailingRatioKey = keyof TrailingRatioUnavailableReasons;

const NEGATIVE_AVERAGE_EXPLANATION: Record<TrailingRatioKey, TranslationKey | null> = {
  pe: null,
  pfcf: null,
  debtToEarnings: "fundamentals.unavailable.negative_earnings",
  debtToFcf: "fundamentals.unavailable.negative_fcf",
};

const NEGATIVE_AVERAGE_SHORT_LABEL: Record<TrailingRatioKey, TranslationKey | null> = {
  pe: null,
  pfcf: null,
  debtToEarnings: "fundamentals.unavailable.negative_earnings_short",
  debtToFcf: "fundamentals.unavailable.negative_fcf_short",
};

/** The translation key of the hover text for a blank ratio cell, or null
 *  when the cell is blank for a reason its row already shows. */
export function unavailableExplanationKey(
  ratioKey: TrailingRatioKey,
  reason: RatioUnavailableReason | null,
): TranslationKey | null {
  if (reason === "insufficient_history") {
    return "fundamentals.unavailable.insufficient_history";
  }
  if (reason === "negative_average") return NEGATIVE_AVERAGE_EXPLANATION[ratioKey];
  return null;
}

/** The translation key of the tiny label shown in place of the dash. Only
 *  a negative window average earns one; everything else keeps the dash. */
export function unavailableShortLabelKey(
  ratioKey: TrailingRatioKey,
  reason: RatioUnavailableReason | null,
): TranslationKey | null {
  if (reason !== "negative_average") return null;
  return NEGATIVE_AVERAGE_SHORT_LABEL[ratioKey];
}
