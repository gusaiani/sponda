import { formatNumber } from "./format";

/** A non-linear mapping for the dual-range slider. The slider talks to the
 * scale in normalized position space (0..1) and stores actual values in
 * value space, so each scale defines both directions plus a snap rule that
 * keeps the displayed numbers tidy. */
export interface SliderScale {
  /** Map a normalized handle position (0..1) to a value. */
  toValue(position: number): number;
  /** Map a value to its normalized handle position (0..1). */
  toPosition(value: number): number;
  /** Round a raw value to the nearest visually-clean increment. */
  snap(value: number): number;
}

const LEVERAGE_LOW_BAND_SHARE = 0.55;
const LEVERAGE_LOG_RANGE = 2;

function snapLeverage(value: number): number {
  if (value <= 0) return 0;
  if (value >= 100) return 100;
  if (value < 1) return Math.round(value * 20) / 20;
  if (value < 20) return Math.round(value * 2) / 2;
  return Math.round(value / 5) * 5;
}

/** Piecewise scale used by the leverage / debt-ratio screener filters.
 * The 0..1 band — where the vast majority of companies sit — gets the
 * first 55% of the track. The 1..100 tail is log-compressed across the
 * remaining 45%, so a handful of distressed outliers can't squash the
 * useful resolution out of the slider. */
export const LEVERAGE_SCALE: SliderScale = {
  toValue(position) {
    if (position <= 0) return 0;
    if (position >= 1) return 100;
    if (position <= LEVERAGE_LOW_BAND_SHARE) {
      return position / LEVERAGE_LOW_BAND_SHARE;
    }
    const highPosition =
      (position - LEVERAGE_LOW_BAND_SHARE) / (1 - LEVERAGE_LOW_BAND_SHARE);
    return Math.pow(10, highPosition * LEVERAGE_LOG_RANGE);
  },
  toPosition(value) {
    if (value <= 0) return 0;
    if (value >= 100) return 1;
    if (value <= 1) {
      return value * LEVERAGE_LOW_BAND_SHARE;
    }
    return (
      LEVERAGE_LOW_BAND_SHARE +
      (Math.log10(value) / LEVERAGE_LOG_RANGE) *
        (1 - LEVERAGE_LOW_BAND_SHARE)
    );
  },
  snap: snapLeverage,
};

/** Format a leverage-ratio value with precision that tracks the snap
 * granularity, so handle labels never read like "0,5500000001". */
export function formatLeverageValue(value: number, locale: string): string {
  if (value < 1) return formatNumber(value, 2, locale);
  if (value < 10) return formatNumber(value, 1, locale);
  return String(Math.round(value));
}
