"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useTranslation } from "../i18n";
import { useLearningMode } from "../learning";
import "../styles/company-grade-card.css";

export interface GradeBreakdown {
  overall: number | null;
  pe10?: number | null;
  pfcf10?: number | null;
  peg?: number | null;
  pfcfPeg?: number | null;
  debtToEquity?: number | null;
  debtExLeaseToEquity?: number | null;
  liabilitiesToEquity?: number | null;
  currentRatio?: number | null;
  debtToAvgEarnings?: number | null;
  debtToAvgFCF?: number | null;
}

interface CompanyGradeCardProps {
  ratings: GradeBreakdown | null | undefined;
}

const PER_INDICATOR_KEYS: Array<keyof GradeBreakdown> = [
  "pe10",
  "pfcf10",
  "peg",
  "pfcfPeg",
  "debtToEquity",
  "debtExLeaseToEquity",
  "liabilitiesToEquity",
  "currentRatio",
  "debtToAvgEarnings",
  "debtToAvgFCF",
];

const TOOLTIP_WIDTH = 280;
const TOOLTIP_GAP = 8;
const VIEWPORT_PADDING = 8;

export function CompanyGradeCard({ ratings }: CompanyGradeCardProps) {
  const { enabled } = useLearningMode();
  const { t } = useTranslation();
  const triggerRef = useRef<HTMLSpanElement>(null);
  const [tooltipVisible, setTooltipVisible] = useState(false);
  const [tooltipPosition, setTooltipPosition] = useState({ top: 0, left: 0 });
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const positionTooltip = useCallback(() => {
    const trigger = triggerRef.current;
    if (!trigger || typeof window === "undefined") return;
    const rect = trigger.getBoundingClientRect();
    const top = rect.bottom + TOOLTIP_GAP;
    const center = rect.left + rect.width / 2;
    let left = center - TOOLTIP_WIDTH / 2;
    const max = window.innerWidth - VIEWPORT_PADDING - TOOLTIP_WIDTH;
    if (left > max) left = max;
    if (left < VIEWPORT_PADDING) left = VIEWPORT_PADDING;
    setTooltipPosition({ top, left });
  }, []);

  const showTooltip = useCallback(() => {
    positionTooltip();
    setTooltipVisible(true);
  }, [positionTooltip]);

  const hideTooltip = useCallback(() => {
    setTooltipVisible(false);
  }, []);

  if (!enabled) return null;

  const overall = ratings?.overall ?? null;

  if (overall == null) {
    return (
      <span className="company-grade-card company-grade-card-empty">
        {t("learning.grade.not_enough_data" as never)}
      </span>
    );
  }

  const tier = Math.max(1, Math.min(5, Math.round(overall)));
  const tierLabel = t(`learning.tier.${tier}` as never);

  const breakdown = ratings
    ? PER_INDICATOR_KEYS
        .map((key) => ({ key, tier: ratings[key] ?? null }))
        .filter((row): row is { key: keyof GradeBreakdown; tier: number } => row.tier !== null)
    : [];
  const introText = t("learning.grade.tooltip.intro" as never).replace(
    "{count}",
    String(breakdown.length),
  );

  return (
    <>
      <span
        ref={triggerRef}
        className={`company-grade-card company-grade-card-tier-${tier}`}
        tabIndex={0}
        onMouseEnter={showTooltip}
        onMouseLeave={hideTooltip}
        onFocus={showTooltip}
        onBlur={hideTooltip}
      >
        <span className="company-grade-card-prefix">
          {t("learning.grade.title" as never)}:{" "}
        </span>
        <span className="company-grade-card-numeral">{tier}</span>
        <span className="company-grade-card-tier-label">{tierLabel}</span>
      </span>
      {mounted && tooltipVisible && createPortal(
        <span
          className="company-grade-card-tooltip"
          role="tooltip"
          style={{
            top: `${tooltipPosition.top}px`,
            left: `${tooltipPosition.left}px`,
            width: `${TOOLTIP_WIDTH}px`,
          }}
        >
          <span className="company-grade-card-tooltip-title">
            {t("learning.grade.tooltip.title" as never)}
          </span>
          <span className="company-grade-card-tooltip-intro">{introText}</span>
          <span className="company-grade-card-tooltip-beta">
            {t("learning.grade.tooltip.beta" as never)}
          </span>
          <ul className="company-grade-card-tooltip-list">
            {breakdown.map((row) => (
              <li key={row.key} className="company-grade-card-tooltip-row">
                <span
                  className={`company-grade-card-tooltip-marker company-grade-card-tooltip-marker-tier-${row.tier}`}
                >
                  {row.tier}
                </span>
                <span className="company-grade-card-tooltip-indicator">
                  {t(`learning.indicator.${row.key}.title` as never)}
                </span>
              </li>
            ))}
          </ul>
          <span className="company-grade-card-tooltip-divider" aria-hidden="true" />
          <span className="company-grade-card-tooltip-disclaimer">
            {t("learning.tooltip.disclaimer" as never)}
          </span>
        </span>,
        document.body,
      )}
    </>
  );
}
