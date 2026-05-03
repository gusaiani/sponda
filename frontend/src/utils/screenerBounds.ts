/**
 * Translate a `DualRangeSlider` change event into the `{min, max}` bound
 * stored on the screener filters object.
 *
 * The slider returns `null` for any handle resting at its track extreme.
 * The screener page used to forward those nulls verbatim, which dropped
 * the corresponding `_min` / `_max` query param — and let values *outside*
 * the visible track sneak past the filter (e.g. a company with negative
 * debt/equity matching a "0..0.5" screen).
 *
 * Filling the missing side with the track bound makes the filter mean
 * what the UI says: "rows whose value lies inside this track range".
 */
export interface SliderTrack {
  trackMin: number;
  trackMax: number;
}

export interface SliderChange {
  min: string | null;
  max: string | null;
}

export function boundFromSliderChange(
  change: SliderChange,
  track: SliderTrack,
): { min: string; max: string } | null {
  if (change.min === null && change.max === null) return null;
  return {
    min: change.min ?? String(track.trackMin),
    max: change.max ?? String(track.trackMax),
  };
}
