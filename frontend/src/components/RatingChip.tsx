"use client";

import { useTranslation } from "../i18n";
import { useLearningMode } from "../learning";
import "../styles/rating-chip.css";

export type RatingTier = 1 | 2 | 3 | 4 | 5;

interface RatingChipProps {
  rating: RatingTier | number | null | undefined;
  indicator: string;
}

export function RatingChip({ rating, indicator }: RatingChipProps) {
  const { enabled } = useLearningMode();
  const { t } = useTranslation();

  if (!enabled) return null;
  if (rating == null) return null;
  const tier = Math.max(1, Math.min(5, Math.round(rating))) as RatingTier;

  const indicatorTitle = t(`learning.indicator.${indicator}.title` as never);
  const tierLabel = t(`learning.tier.${tier}` as never);
  const description = t(`learning.indicator.${indicator}.description` as never);

  return (
    <span
      className={`rating-chip rating-chip-tier-${tier}`}
      role="img"
      aria-label={`${indicatorTitle} · ${tierLabel}`}
      tabIndex={0}
    >
      <span className="rating-chip-numeral">{tier}</span>
      <span className="rating-chip-tooltip" role="tooltip">
        <span className="rating-chip-tooltip-title">{indicatorTitle}</span>
        <span className="rating-chip-tooltip-tier">{tierLabel}</span>
        {description ? (
          <span className="rating-chip-tooltip-description">{description}</span>
        ) : null}
      </span>
    </span>
  );
}
