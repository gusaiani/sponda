"use client";

import { useAuth } from "../hooks/useAuth";
import { useRevisitSchedules, useVisits } from "../hooks/useVisits";
import { useTranslation } from "../i18n";
import "../styles/revisit-banner.css";

interface RevisitBannerProps {
  ticker: string;
}

export function RevisitBanner({ ticker }: RevisitBannerProps) {
  const { t } = useTranslation();
  const { isAuthenticated } = useAuth();
  const { getScheduleForTicker } = useRevisitSchedules();
  const { markVisited } = useVisits();

  if (!isAuthenticated) return null;

  const schedule = getScheduleForTicker(ticker);
  if (!schedule) return null;

  const today = new Date().toISOString().slice(0, 10);
  const isDue = schedule.next_revisit <= today;
  if (!isDue) return null;

  const isOverdue = schedule.next_revisit < today;
  const message = isOverdue
    ? t("visits.banner_overdue", { date: schedule.next_revisit })
    : t("visits.banner_due");

  function handleMarkVisited() {
    markVisited.mutate({ ticker });
  }

  return (
    <div className={`revisit-banner ${isOverdue ? "revisit-banner-overdue" : ""}`}>
      <span className="revisit-banner-text">{message}</span>
      <button className="revisit-banner-action" onClick={handleMarkVisited} type="button">
        {t("visits.mark_visited")}
      </button>
    </div>
  );
}
