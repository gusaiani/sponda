/**
 * Debt-coverage indicators are the only screener columns whose meaning
 * depends on a request parameter: `debt_window_years` makes them average
 * exactly N years, and without it they average up to 10. The column
 * label carries that horizon so the table never shows a number whose
 * denominator the reader cannot tell.
 */
export const DEBT_WINDOW_MIN_YEARS = 1;
export const DEBT_WINDOW_MAX_YEARS = 15;
export const DEBT_WINDOW_LOOSE_MAX_YEARS = 10;

export const DEBT_WINDOW_OPTIONS: readonly number[] = Array.from(
  { length: DEBT_WINDOW_MAX_YEARS - DEBT_WINDOW_MIN_YEARS + 1 },
  (_, index) => DEBT_WINDOW_MIN_YEARS + index,
);

export const DEBT_COVERAGE_INDICATORS = [
  "debt_to_avg_earnings",
  "debt_to_avg_fcf",
] as const;

export type DebtCoverageIndicator = (typeof DEBT_COVERAGE_INDICATORS)[number];

export function isDebtCoverageIndicator(
  indicator: string,
): indicator is DebtCoverageIndicator {
  return (DEBT_COVERAGE_INDICATORS as readonly string[]).includes(indicator);
}

/** "Debt / Avg FCF" → "Debt / Avg FCF (5y)", or "(≤10y)" for the loose default. */
export function debtCoverageLabel(
  baseLabel: string,
  debtWindowYears: number | null | undefined,
): string {
  if (debtWindowYears === null || debtWindowYears === undefined) {
    return `${baseLabel} (≤${DEBT_WINDOW_LOOSE_MAX_YEARS}y)`;
  }
  return `${baseLabel} (${debtWindowYears}y)`;
}

/** Coerce a `<select>` value back into a window, `null` for the loose option. */
export function parseDebtWindowYears(rawValue: string): number | null {
  if (rawValue === "") return null;
  const years = Number(rawValue);
  if (!Number.isInteger(years)) return null;
  if (years < DEBT_WINDOW_MIN_YEARS || years > DEBT_WINDOW_MAX_YEARS) return null;
  return years;
}
