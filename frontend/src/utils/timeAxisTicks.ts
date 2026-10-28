/**
 * X-axis ticks for the expanded indicator chart.
 *
 * Long windows get a tick per year. A one- or two-year window has at most two
 * year boundaries, which left the axis with a lone "26" at its left edge, so
 * short windows get a tick per month instead.
 */
import { formatPriceDate } from "./dateLabels";

export type TimeAxisGranularity = "month" | "year";

export interface TimeAxisTicks {
  ticks: number[];
  granularity: TimeAxisGranularity;
}

const MILLISECONDS_PER_DAY = 86_400_000;

/** Windows up to two years long are ticked by month. */
const MONTHLY_TICKS_MAXIMUM_SPAN_DAYS = 2 * 366;

function periodKey(timestamp: number, granularity: TimeAxisGranularity): string {
  const date = new Date(timestamp);
  const year = date.getUTCFullYear();
  return granularity === "year" ? String(year) : `${year}-${date.getUTCMonth()}`;
}

/** First timestamp of every month or year in an ascending series, thinned to `maximumTicks`. */
export function buildTimeAxisTicks(timestamps: number[], maximumTicks: number): TimeAxisTicks {
  const spanDays = timestamps.length
    ? (timestamps[timestamps.length - 1] - timestamps[0]) / MILLISECONDS_PER_DAY
    : 0;
  const granularity: TimeAxisGranularity =
    spanDays <= MONTHLY_TICKS_MAXIMUM_SPAN_DAYS ? "month" : "year";

  let ticks: number[] = [];
  let previousPeriod = "";
  for (const timestamp of timestamps) {
    const period = periodKey(timestamp, granularity);
    if (period !== previousPeriod) ticks.push(timestamp);
    previousPeriod = period;
  }
  if (ticks.length > maximumTicks) {
    const step = Math.ceil(ticks.length / maximumTicks);
    ticks = ticks.filter((_, tickPosition) => tickPosition % step === 0);
  }
  return { ticks, granularity };
}

export function formatTimeAxisTick(
  timestamp: number,
  granularity: TimeAxisGranularity,
  locale: string,
): string {
  const isoDate = new Date(timestamp).toISOString().slice(0, 10);
  if (granularity === "year") return isoDate.slice(2, 4);
  return formatPriceDate(isoDate, locale);
}
