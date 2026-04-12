"use client";

import { useState } from "react";
import Link from "next/link";
import { useAuth } from "../../../hooks/useAuth";
import { useVisits, useRevisitSchedules, type VisitEntry, type RevisitScheduleEntry } from "../../../hooks/useVisits";
import { useTranslation } from "../../../i18n";
import { logoUrl } from "../../../utils/format";
import "../../../styles/visits-page.css";

function ScheduleCard({ schedule, locale }: { schedule: RevisitScheduleEntry; locale: string }) {
  const { t } = useTranslation();
  const today = new Date().toISOString().slice(0, 10);
  const isOverdue = schedule.next_revisit < today;
  const isDueToday = schedule.next_revisit === today;

  let statusLabel = "";
  if (isDueToday) statusLabel = t("visits.due_today");
  else if (isOverdue) {
    const daysOverdue = Math.floor((Date.now() - new Date(schedule.next_revisit).getTime()) / 86400000);
    statusLabel = t("visits.days_overdue", { count: String(daysOverdue) });
  }

  return (
    <Link href={`/${locale}/${schedule.ticker}`} className="visit-card">
      <img className="visit-card-logo" src={logoUrl(schedule.ticker)} alt="" loading="lazy"
        onError={(event) => { (event.target as HTMLImageElement).style.display = "none"; }} />
      <div className="visit-card-info">
        <span className="visit-card-ticker">{schedule.ticker}</span>
        <span className="visit-card-date">{schedule.next_revisit}</span>
      </div>
      {(isDueToday || isOverdue) && (
        <span className={`visit-card-badge ${isOverdue ? "visit-card-badge-overdue" : ""}`}>
          {statusLabel}
        </span>
      )}
      {schedule.recurrence_days && (
        <span className="visit-card-recurrence">
          {schedule.recurrence_days}d
        </span>
      )}
    </Link>
  );
}

function VisitRow({ visit, locale }: { visit: VisitEntry; locale: string }) {
  return (
    <Link href={`/${locale}/${visit.ticker}`} className="visit-row">
      <img className="visit-row-logo" src={logoUrl(visit.ticker)} alt="" loading="lazy"
        onError={(event) => { (event.target as HTMLImageElement).style.display = "none"; }} />
      <span className="visit-row-ticker">{visit.ticker}</span>
      <span className="visit-row-date">{visit.visited_at}</span>
      {visit.note && <span className="visit-row-note">{visit.note}</span>}
    </Link>
  );
}

export default function VisitsPage() {
  const { t, locale } = useTranslation();
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const { visits, isLoading: visitsLoading } = useVisits();
  const { schedules, isLoading: schedulesLoading } = useRevisitSchedules();
  const [groupByCompany, setGroupByCompany] = useState(false);

  if (authLoading || visitsLoading || schedulesLoading) {
    return (
      <div className="visits-page">
        <p className="visits-page-loading">{t("common.loading")}</p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="visits-page">
        <h1 className="visits-page-title">{t("visits.page_title")}</h1>
        <p className="visits-page-text">{t("visits.must_login")}</p>
        <p className="auth-link">
          <Link href={`/${locale}/login`}>{t("auth.do_login")}</Link>
        </p>
      </div>
    );
  }

  const today = new Date().toISOString().slice(0, 10);
  const visitedTodayTickers = new Set(
    visits.filter((visit) => visit.visited_at === today).map((visit) => visit.ticker),
  );
  const dueSchedules = schedules.filter(
    (schedule) => schedule.next_revisit <= today && !visitedTodayTickers.has(schedule.ticker),
  );
  const futureSchedules = schedules.filter((schedule) => schedule.next_revisit > today);

  // Group visits by company
  const visitsByCompany = new Map<string, VisitEntry[]>();
  if (groupByCompany) {
    for (const visit of visits) {
      const existing = visitsByCompany.get(visit.ticker) ?? [];
      existing.push(visit);
      visitsByCompany.set(visit.ticker, existing);
    }
  }

  return (
    <div className="visits-page">
      <h1 className="visits-page-title">{t("visits.page_title")}</h1>

      {/* Upcoming revisits */}
      <section className="visits-section">
        <h2 className="visits-section-heading">{t("visits.upcoming")}</h2>
        {dueSchedules.length === 0 && futureSchedules.length === 0 ? (
          <p className="visits-empty">{t("visits.no_upcoming")}</p>
        ) : (
          <div className="visits-grid">
            {dueSchedules.map((schedule) => (
              <ScheduleCard key={schedule.id} schedule={schedule} locale={locale} />
            ))}
            {futureSchedules.map((schedule) => (
              <ScheduleCard key={schedule.id} schedule={schedule} locale={locale} />
            ))}
          </div>
        )}
      </section>

      {/* Visit history */}
      <section className="visits-section">
        <div className="visits-section-header">
          <h2 className="visits-section-heading">{t("visits.history")}</h2>
          <button
            className={`visits-group-toggle ${groupByCompany ? "visits-group-toggle-active" : ""}`}
            onClick={() => setGroupByCompany(!groupByCompany)}
            type="button"
          >
            {t("visits.group_by_company")}
          </button>
        </div>

        {visits.length === 0 ? (
          <p className="visits-empty">{t("visits.no_visits")}</p>
        ) : groupByCompany ? (
          <div className="visits-grouped">
            {[...visitsByCompany.entries()].map(([ticker, companyVisits]) => (
              <div key={ticker} className="visits-company-group">
                <h3 className="visits-company-heading">{ticker}</h3>
                {companyVisits.map((visit) => (
                  <VisitRow key={visit.id} visit={visit} locale={locale} />
                ))}
              </div>
            ))}
          </div>
        ) : (
          <div className="visits-list">
            {visits.map((visit) => (
              <VisitRow key={visit.id} visit={visit} locale={locale} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
