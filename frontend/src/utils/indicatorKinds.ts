/**
 * Classify each chartable indicator so the comparison chart knows how to
 * overlay it across companies and currencies.
 *
 * - `currency-abs-level`: an absolute, currency-denominated value whose level is
 *   arbitrary across companies (share price depends on split history). Must be
 *   rebased to a common base before comparing.
 * - `currency-abs-size`: an absolute, currency-denominated value whose magnitude
 *   is meaningful (market cap = company size). Comparable only after rebasing or
 *   converting to a common currency.
 * - `ratio`: a dimensionless multiple/ratio (P/L, D/E, current ratio, …). Already
 *   currency-neutral, so it overlays raw — rebasing would destroy the comparison.
 * - `percent`: a percentage (CAGR, ROE). Currency-neutral; overlays raw.
 *
 * The metric ids match `METRIC_IDS` in CompanyMetricsCard.
 */
export type IndicatorKind =
  | "currency-abs-level"
  | "currency-abs-size"
  | "ratio"
  | "percent";

const KIND_BY_METRIC_ID: Record<string, IndicatorKind> = {
  "current-price": "currency-abs-level",
  "market-cap": "currency-abs-size",
  "pe10": "ratio",
  "pfcf10": "ratio",
  "peg": "ratio",
  "pfcfg": "ratio",
  "gross-debt-eq": "ratio",
  "debt-ex-lease-eq": "ratio",
  "liab-eq": "ratio",
  "gross-debt-earnings": "ratio",
  "gross-debt-fcf": "ratio",
  "current-ratio": "ratio",
  "cagr-earnings": "percent",
  "cagr-fcf": "percent",
};

/** Kind for a metric id; unknown ids default to `ratio` (overlay raw, safest). */
export function indicatorKind(metricId: string): IndicatorKind {
  return KIND_BY_METRIC_ID[metricId] ?? "ratio";
}

/** Whether a metric should be rebased (indexed) when overlaying companies.
 * Only the absolute, currency-denominated indicators are rebasable. */
export function isRebasable(kind: IndicatorKind): boolean {
  return kind === "currency-abs-level" || kind === "currency-abs-size";
}
