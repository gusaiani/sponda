import { currencySymbol, formatNumber, formatNumberUpTo } from "./format";

/**
 * Indicator alert thresholds are stored in the indicator's raw unit (a market
 * cap of R$ 3 billion is stored as 3000000000). Typing nine zeros is
 * error-prone, so the UI lets users enter market caps in millions. This
 * module is the single place that knows which indicators are scaled and how
 * to convert between the entered unit and the stored one.
 */
export const MILLION = 1_000_000;

/** Backend DecimalField(decimal_places=6): round to this before sending. */
const STORED_DECIMAL_PLACES = 6;

const THRESHOLD_UNIT_BY_INDICATOR: Record<string, number> = {
  market_cap: MILLION,
};

const CURRENCY_INDICATORS = new Set(["current_price", "market_cap"]);

const PRICE_DECIMALS = 2;
const RATIO_MAX_DECIMALS = 2;
const MILLIONS_MAX_DECIMALS = 2;

/** Multiplier from the unit the user types in to the unit the backend stores. */
export function thresholdUnit(indicator: string): number {
  return THRESHOLD_UNIT_BY_INDICATOR[indicator] ?? 1;
}

export function isThresholdInMillions(indicator: string): boolean {
  return thresholdUnit(indicator) === MILLION;
}

function roundToStoredPrecision(value: number): number {
  const factor = 10 ** STORED_DECIMAL_PLACES;
  return Math.round(value * factor) / factor;
}

/** Convert the text the user typed into the string the API expects. */
export function toStoredThreshold(indicator: string, enteredText: string): string {
  const entered = enteredText.trim();
  const unit = thresholdUnit(indicator);
  if (unit === 1) return entered;
  return String(roundToStoredPrecision(Number(entered) * unit));
}

/** Convert a stored threshold back into the unit the user types in. */
export function fromStoredThreshold(indicator: string, storedThreshold: string): number {
  return Number(storedThreshold) / thresholdUnit(indicator);
}

/**
 * Human-readable threshold for lists and notifications: market caps in
 * millions with an "M" suffix, prices with two decimals, ratios trimmed of
 * trailing zeros. Non-numeric input is returned untouched.
 */
export function formatAlertThreshold(
  indicator: string,
  storedThreshold: string,
  ticker: string,
  locale: string,
): string {
  const value = Number(storedThreshold);
  if (storedThreshold.trim() === "" || !Number.isFinite(value)) return storedThreshold;

  if (isThresholdInMillions(indicator)) {
    const millions = fromStoredThreshold(indicator, storedThreshold);
    return `${currencySymbol(ticker)} ${formatNumberUpTo(millions, MILLIONS_MAX_DECIMALS, locale)}M`;
  }
  if (CURRENCY_INDICATORS.has(indicator)) {
    return `${currencySymbol(ticker)} ${formatNumber(value, PRICE_DECIMALS, locale)}`;
  }
  return formatNumberUpTo(value, RATIO_MAX_DECIMALS, locale);
}
