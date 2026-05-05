"use client";

import { useCallback, useRef, useState } from "react";
import { useTranslation } from "../i18n";
import { useLearningMode } from "../learning";
import { tierRanges } from "../learning/criteria";
import "../styles/rating-chip.css";

export type RatingTier = 1 | 2 | 3 | 4 | 5;

interface RatingChipProps {
  rating: RatingTier | number | null | undefined;
  indicator: string;
}

const TOOLTIP_WIDTH = 260;
const VIEWPORT_PADDING = 8;

export function RatingChip({ rating, indicator }: RatingChipProps) {
  const { enabled } = useLearningMode();
  const { t, locale } = useTranslation();
  const containerRef = useRef<HTMLSpanElement>(null);
  const [horizontalShift, setHorizontalShift] = useState(0);

  const adjustPosition = useCallback(() => {
    const chip = containerRef.current;
    if (!chip || typeof window === "undefined") return;
    const chipRect = chip.getBoundingClientRect();
    const center = chipRect.left + chipRect.width / 2;
    const left = center - TOOLTIP_WIDTH / 2;
    const right = center + TOOLTIP_WIDTH / 2;
    const max = window.innerWidth - VIEWPORT_PADDING;
    if (right > max) setHorizontalShift(max - right);
    else if (left < VIEWPORT_PADDING) setHorizontalShift(VIEWPORT_PADDING - left);
    else setHorizontalShift(0);
  }, []);

  if (!enabled) return null;
  if (rating == null) return null;
  const tier = Math.max(1, Math.min(5, Math.round(rating))) as RatingTier;

  const indicatorTitle = t(`learning.indicator.${indicator}.title` as never);
  const tierLabel = t(`learning.tier.${tier}` as never);
  const ranges = tierRanges(indicator, locale);

  return (
    <span
      ref={containerRef}
      className={`rating-chip rating-chip-tier-${tier}`}
      role="img"
      aria-label={`${indicatorTitle} · ${tierLabel}`}
      tabIndex={0}
      onMouseEnter={adjustPosition}
      onFocus={adjustPosition}
    >
      <span className="rating-chip-numeral">{tier}</span>
      <span
        className="rating-chip-tooltip"
        role="tooltip"
        style={{ transform: `translateX(calc(-50% + ${horizontalShift}px))` }}
      >
        <span className="rating-chip-tooltip-title">{indicatorTitle}</span>
        <ul className="rating-chip-tooltip-list">
          {ranges.map((row) => (
            <li
              key={row.tier}
              className={`rating-chip-tooltip-row${row.tier === tier ? " rating-chip-tooltip-row--current" : ""}`}
            >
              <span className={`rating-chip-tooltip-marker rating-chip-tooltip-marker-tier-${row.tier}`}>
                {row.tier}
              </span>
              <span className="rating-chip-tooltip-range">{row.range}</span>
              <span className="rating-chip-tooltip-tier-label">
                {t(`learning.tier.${row.tier}` as never)}
              </span>
            </li>
          ))}
        </ul>
        <span className="rating-chip-tooltip-divider" aria-hidden="true" />
        <span className="rating-chip-tooltip-disclaimer">
          {t("learning.tooltip.disclaimer" as never)}
        </span>
      </span>
    </span>
  );
}
