"use client";

import { useTranslation } from "../i18n";
import { useLearningMode } from "../learning";
import "../styles/company-grade-card.css";

interface CompanyGradeCardProps {
  overall: number | null | undefined;
}

export function CompanyGradeCard({ overall }: CompanyGradeCardProps) {
  const { enabled } = useLearningMode();
  const { t } = useTranslation();

  if (!enabled) return null;

  if (overall == null) {
    return (
      <div className="company-grade-card company-grade-card-empty">
        <span className="company-grade-card-empty-text">
          {t("learning.grade.not_enough_data" as never)}
        </span>
      </div>
    );
  }

  const tier = Math.max(1, Math.min(5, Math.round(overall)));
  const tierLabel = t(`learning.tier.${tier}` as never);

  return (
    <div className={`company-grade-card company-grade-card-tier-${tier}`}>
      <div className="company-grade-card-numeral">{tier}</div>
      <div className="company-grade-card-content">
        <div className="company-grade-card-title">{t("learning.grade.title" as never)}</div>
        <div className="company-grade-card-tier-label">{tierLabel}</div>
        <div className="company-grade-card-caption">
          {t("learning.grade.caption" as never)}
        </div>
      </div>
    </div>
  );
}
