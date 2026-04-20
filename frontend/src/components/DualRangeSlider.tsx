import { formatNumber } from "../utils/format";
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
  onChange: (value: DualRangeValue) => void;
  format?: (value: number) => string;
  locale?: string;
}

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
  format,
  locale = "en",
}: Props) {
  const minNumeric = minValue !== null ? Number(minValue) : trackMin;
  const maxNumeric = maxValue !== null ? Number(maxValue) : trackMax;

  const span = trackMax - trackMin;
  const leftPct = span === 0 ? 0 : ((minNumeric - trackMin) / span) * 100;
  const rightPct = span === 0 ? 0 : ((trackMax - maxNumeric) / span) * 100;

  function handleMinChange(event: React.ChangeEvent<HTMLInputElement>) {
    const raw = Number(event.target.value);
    // Clamp the min handle so it can never pass the max handle — a common
    // dual-range UX concession since the two handles share a single axis.
    const clamped = Math.min(raw, maxNumeric);
    onChange({
      min: toStoredValue(clamped, trackMin),
      max: toStoredValue(maxNumeric, trackMax),
    });
  }

  function handleMaxChange(event: React.ChangeEvent<HTMLInputElement>) {
    const raw = Number(event.target.value);
    const clamped = Math.max(raw, minNumeric);
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
          min={trackMin}
          max={trackMax}
          step={step}
          value={minNumeric}
          onChange={handleMinChange}
          className="dual-range-input dual-range-input-min"
          aria-label="Minimum"
        />
        <input
          type="range"
          min={trackMin}
          max={trackMax}
          step={step}
          value={maxNumeric}
          onChange={handleMaxChange}
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
