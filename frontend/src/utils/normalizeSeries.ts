import type { DataPoint } from "../components/MiniChart";

/** A company's series for one indicator, ready to overlay. */
export interface NamedSeries {
  ticker: string;
  name: string;
  color: string;
  currency: string;
  points: DataPoint[];
}

/** A single FX anchor: `rate` units of the target currency per 1 source unit. */
export interface FxPoint {
  date: string;
  rate: number;
}

/** One row of the aligned dataset: a timestamp plus one value per ticker. */
export interface AlignedRow {
  t: number;
  label: string;
  [ticker: string]: number | string | null;
}

export interface AlignedDataset {
  rows: AlignedRow[];
  tickers: string[];
}

const MS_PER_DAY = 86_400_000;

/** Parse a series label into a sortable timestamp.
 * Year-only labels ("2024") anchor to that year's end so they interleave with
 * dated labels ("2024-01-31") on a single time axis. */
export function labelToTimestamp(label: string): number {
  if (/^\d{4}$/.test(label)) return Date.parse(`${label}-12-31T00:00:00Z`);
  return Date.parse(`${label}T00:00:00Z`);
}

/** Format a timestamp back to a YYYY-MM-DD label for tooltips/axes. */
export function timestampToLabel(t: number): string {
  return new Date(t).toISOString().slice(0, 10);
}

interface TimedValue {
  t: number;
  value: number;
}

/** Last value at or before `t` via binary search; null if `t` precedes all. */
function stepValueAt(sorted: TimedValue[], t: number): number | null {
  let low = 0;
  let high = sorted.length - 1;
  let answer = -1;
  while (low <= high) {
    const mid = (low + high) >> 1;
    if (sorted[mid].t <= t) {
      answer = mid;
      low = mid + 1;
    } else {
      high = mid - 1;
    }
  }
  return answer >= 0 ? sorted[answer].value : null;
}

/**
 * Translate a value series into another currency using a step-sampled FX path.
 * For each point, the rate is the latest anchor at or before that date; dates
 * before the first anchor fall back to the first anchor (an approximation the
 * UI flags). An empty FX path means identity (same currency) — returned as-is.
 */
export function convertSeries(points: DataPoint[], fx: FxPoint[]): DataPoint[] {
  if (!fx.length || !points.length) return points;
  const sorted: TimedValue[] = fx
    .map((point) => ({ t: labelToTimestamp(point.date), value: point.rate }))
    .sort((a, b) => a.t - b.t);
  const firstRate = sorted[0].value;
  return points.map((point) => {
    const rate = stepValueAt(sorted, labelToTimestamp(point.label)) ?? firstRate;
    return { ...point, value: point.value * rate };
  });
}

/**
 * Merge several companies' series onto one time axis so a single dataset can
 * drive every line (and the shared tooltip).
 *
 * The axis starts at the latest common start date (so every series has a value
 * from the first row — the honest origin for rebasing) and steps through the
 * union of all timestamps after it, carrying each series forward with its last
 * known value. With `rebase`, every series is divided by its value at that
 * common origin and scaled to 100, neutralizing arbitrary price levels and
 * currency units so curves are directly comparable.
 */
export function buildAlignedDataset(
  series: NamedSeries[],
  options: { rebase?: boolean } = {},
): AlignedDataset {
  const active = series.filter((entry) => entry.points.length > 0);
  if (!active.length) return { rows: [], tickers: [] };

  const prepared = active.map((entry) => ({
    ticker: entry.ticker,
    points: entry.points
      .map((point) => ({ t: labelToTimestamp(point.label), value: point.value }))
      .sort((a, b) => a.t - b.t),
  }));

  const commonStart = Math.max(...prepared.map((entry) => entry.points[0].t));

  const timestamps = new Set<number>([commonStart]);
  for (const entry of prepared) {
    for (const point of entry.points) {
      if (point.t >= commonStart) timestamps.add(point.t);
    }
  }
  const sortedTimestamps = [...timestamps].sort((a, b) => a - b);

  const bases = new Map<string, number | null>();
  if (options.rebase) {
    for (const entry of prepared) {
      bases.set(entry.ticker, stepValueAt(entry.points, commonStart));
    }
  }

  const rows: AlignedRow[] = sortedTimestamps.map((t) => {
    const row: AlignedRow = { t, label: timestampToLabel(t) };
    for (const entry of prepared) {
      let value = stepValueAt(entry.points, t);
      if (value !== null && options.rebase) {
        const base = bases.get(entry.ticker);
        value = base && base > 0 ? (value / base) * 100 : null;
      }
      row[entry.ticker] = value;
    }
    return row;
  });

  return { rows, tickers: prepared.map((entry) => entry.ticker) };
}

/** Whether the supplied series span more than one currency. */
export function hasMixedCurrencies(series: NamedSeries[]): boolean {
  const currencies = new Set(series.map((entry) => entry.currency));
  return currencies.size > 1;
}

export { MS_PER_DAY };
