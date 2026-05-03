import { formatNumber } from "../utils/format";
import type { SliderScale } from "../utils/sliderScale";
import "../styles/dual-range-slider.css";

export interface DualRangeValue {
  min: string | null;
  max: string | null;
}

interface Props {
  trackMin: number;
  trackMax: number;
  step: number;
  minValue: string | null;
  maxValue: string | null;
  /** Fires on every drag tick + keystroke — use for live visual state
   * (handle position, value labels). */
  onChange: (value: DualRangeValue) => void;
  /** Fires once when the user releases the handle (pointerup) or
   * finishes a keyboard adjustment (keyup). Use for expensive side
   * effects like network requests so we don't fire one per drag tick. */
  onCommit?: () => void;
  format?: (value: number) => string;
  locale?: string;
  scale?: SliderScale;
}

/** Number of integer stops the underlying <input> uses when a non-linear
 * scale is in play. We work in normalized position space (0..1) and quantize
 * to this resolution so the native range input still has integer steps. */
export const SLIDER_SCALE_RESOLUTION = 1000;

/** Render `value` using the supplied formatter, or fall back to the default
 * short numeric form. Kept as a helper so the range and value labels stay
 * aligned without repeating the fallback logic. */
function formatValue(value: number, locale: string, format?: (value: number) => string): string {
  if (format) return format(value);
  if (Number.isInteger(value)) return String(value);
  return formatNumber(value, 1, locale);
}

/** Given a raw handle number and whether it sits at the track extreme,
 * return the string we want to store (or null to clear that side). This is
 * the convention the screener page relies on: a null bound is treated as
 * "no filter" by `buildScreenerQuery`. */
function toStoredValue(
  numeric: number,
  extreme: number,
): string | null {
  if (numeric === extreme) return null;
  return String(numeric);
}

export function DualRangeSlider({
  trackMin,
  trackMax,
  step,
  minValue,
  maxValue,
  onChange,
  onCommit,
  format,
  locale = "en",
  scale,
}: Props) {
  const handleCommit = onCommit ? () => onCommit() : undefined;
  const minNumeric = minValue !== null ? Number(minValue) : trackMin;
  const maxNumeric = maxValue !== null ? Number(maxValue) : trackMax;

  const span = trackMax - trackMin;
  const valueToFraction = scale
    ? (value: number) => scale.toPosition(value)
    : (value: number) => (span === 0 ? 0 : (value - trackMin) / span);

  const minFraction = valueToFraction(minNumeric);
  const maxFraction = valueToFraction(maxNumeric);
  const leftPct = minFraction * 100;
  const rightPct = (1 - maxFraction) * 100;

  // When a scale is active the native input runs in position space (integer
  // stops 0..N); otherwise it runs in value space with the original step.
  const inputMin = scale ? 0 : trackMin;
  const inputMax = scale ? SLIDER_SCALE_RESOLUTION : trackMax;
  const inputStep = scale ? 1 : step;
  const minInputValue = scale
    ? Math.round(minFraction * SLIDER_SCALE_RESOLUTION)
    : minNumeric;
  const maxInputValue = scale
    ? Math.round(maxFraction * SLIDER_SCALE_RESOLUTION)
    : maxNumeric;

  function rawToValue(raw: number): number {
    if (!scale) return raw;
    const position = raw / SLIDER_SCALE_RESOLUTION;
    return scale.snap(scale.toValue(position));
  }

  function handleMinChange(event: React.ChangeEvent<HTMLInputElement>) {
    const raw = Number(event.target.value);
    const candidate = rawToValue(raw);
    // Clamp the min handle so it can never pass the max handle — a common
    // dual-range UX concession since the two handles share a single axis.
    const clamped = Math.min(candidate, maxNumeric);
    onChange({
      min: toStoredValue(clamped, trackMin),
      max: toStoredValue(maxNumeric, trackMax),
    });
  }

  function handleMaxChange(event: React.ChangeEvent<HTMLInputElement>) {
    const raw = Number(event.target.value);
    const candidate = rawToValue(raw);
    const clamped = Math.max(candidate, minNumeric);
    onChange({
      min: toStoredValue(minNumeric, trackMin),
      max: toStoredValue(clamped, trackMax),
    });
  }

  return (
    <div className="dual-range">
      <span className="dual-range-label dual-range-label-min">
        {formatValue(minNumeric, locale, format)}
      </span>
      <div className="dual-range-track">
        <div
          className="dual-range-fill"
          style={{ left: `${leftPct}%`, right: `${rightPct}%` }}
        />
        <input
          type="range"
          min={inputMin}
          max={inputMax}
          step={inputStep}
          value={minInputValue}
          onChange={handleMinChange}
          onPointerUp={handleCommit}
          onKeyUp={handleCommit}
          className="dual-range-input dual-range-input-min"
          aria-label="Minimum"
        />
        <input
          type="range"
          min={inputMin}
          max={inputMax}
          step={inputStep}
          value={maxInputValue}
          onChange={handleMaxChange}
          onPointerUp={handleCommit}
          onKeyUp={handleCommit}
          className="dual-range-input dual-range-input-max"
          aria-label="Maximum"
        />
      </div>
      <span className="dual-range-label dual-range-label-max">
        {formatValue(maxNumeric, locale, format)}
      </span>
    </div>
  );
}
