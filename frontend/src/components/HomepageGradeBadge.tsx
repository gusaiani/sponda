"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useTranslation } from "../i18n";
import { useLearningMode } from "../learning";
import type { GradeBreakdown } from "./CompanyGradeCard";
import "../styles/homepage-grade-badge.css";

interface HomepageGradeBadgeProps {
  ratings: GradeBreakdown | null | undefined;
  /** Term (in years) used to derive the ratings — surfaced in the tooltip
   *  so users know which window the grade was computed over. Optional so
   *  callers that don't track an effective window can omit it. */
  years?: number;
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

export function HomepageGradeBadge({ ratings, years }: HomepageGradeBadgeProps) {
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
  if (overall == null) return null;

  const tier = Math.max(1, Math.min(5, Math.round(overall)));

  const breakdown = ratings
    ? PER_INDICATOR_KEYS
        .map((key) => ({ key, tier: ratings[key] ?? null }))
        .filter((row): row is { key: keyof GradeBreakdown; tier: number } => row.tier !== null)
    : [];
  const introText = t("learning.grade.tooltip.intro" as never).replace(
    "{count}",
    String(breakdown.length),
  );
  const termText = years != null
    ? t("learning.grade.tooltip.term" as never).replace("{years}", String(years))
    : null;

  return (
    <>
      <span
        ref={triggerRef}
        className={`homepage-grade-badge homepage-grade-badge-tier-${tier}`}
        tabIndex={0}
        role="img"
        aria-label={t("learning.grade.title" as never) + ` ${tier}`}
        onMouseEnter={showTooltip}
        onMouseLeave={hideTooltip}
        onFocus={showTooltip}
        onBlur={hideTooltip}
        onClick={(e) => e.preventDefault()}
      >
        <span className="homepage-grade-badge-numeral">{tier}</span>
      </span>
      {mounted && tooltipVisible && createPortal(
        <span
          className="homepage-grade-badge-tooltip"
          role="tooltip"
          style={{
            top: `${tooltipPosition.top}px`,
            left: `${tooltipPosition.left}px`,
            width: `${TOOLTIP_WIDTH}px`,
          }}
        >
          <span className="homepage-grade-badge-tooltip-title">
            {t("learning.grade.tooltip.title" as never)}
          </span>
          <span className="homepage-grade-badge-tooltip-intro">{introText}</span>
          {termText && (
            <span className="homepage-grade-badge-tooltip-term">{termText}</span>
          )}
          <span className="homepage-grade-badge-tooltip-beta">
            {t("learning.grade.tooltip.beta" as never)}
          </span>
          <ul className="homepage-grade-badge-tooltip-list">
            {breakdown.map((row) => (
              <li key={row.key} className="homepage-grade-badge-tooltip-row">
                <span
                  className={`homepage-grade-badge-tooltip-marker homepage-grade-badge-tooltip-marker-tier-${row.tier}`}
                >
                  {row.tier}
                </span>
                <span className="homepage-grade-badge-tooltip-indicator">
                  {t(`learning.indicator.${row.key}.title` as never)}
                </span>
              </li>
            ))}
          </ul>
          <span className="homepage-grade-badge-tooltip-divider" aria-hidden="true" />
          <span className="homepage-grade-badge-tooltip-disclaimer">
            {t("learning.tooltip.disclaimer" as never)}
          </span>
        </span>,
        document.body,
      )}
    </>
  );
}
