"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useAuth } from "../../../hooks/useAuth";
import { usePendingReminders, useRemindersList } from "../../../hooks/useVisits";
import { useTranslation } from "../../../i18n";
import { localToday, logoUrl } from "../../../utils/format";
import "../../../styles/notifications-page.css";

const PAGE_SIZE = 30;

export default function NotificationsPage() {
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const { t, locale } = useTranslation();
  const params = useParams<{ locale: string }>();
  const currentLocale = params.locale || locale;
  const [page, setPage] = useState(1);
  const { data, isLoading } = useRemindersList(page);
  const { dismissReminder, dismissAllReminders } = usePendingReminders();

  if (authLoading) {
    return <div className="notifications-page" />;
  }

  if (!isAuthenticated) {
    return (
      <div className="notifications-page">
        <p className="notifications-empty">
          <Link href={`/${currentLocale}/login`}>{t("auth.login")}</Link>
        </p>
      </div>
    );
  }

  const count = data?.count ?? 0;
  const schedules = data?.schedules ?? [];
  const totalPages = Math.max(1, Math.ceil(count / PAGE_SIZE));
  const today = localToday();

  return (
    <div className="notifications-page">
      <div className="notifications-header">
        <h1 className="notifications-title">{t("notifications.page_title")}</h1>
        {count > 0 && (
          <button
            className="notifications-mark-all"
            type="button"
            onClick={() => dismissAllReminders.mutate()}
            disabled={dismissAllReminders.isPending}
          >
            {t("notifications.mark_all_seen")}
          </button>
        )}
      </div>

      {isLoading && <p className="notifications-empty">{t("common.loading")}</p>}

      {!isLoading && count === 0 && (
        <p className="notifications-empty">{t("notifications.no_pending")}</p>
      )}

      {!isLoading && schedules.length > 0 && (
        <ul className="notifications-list">
          {schedules.map((schedule) => {
            const isOverdue = schedule.next_revisit < today;
            return (
              <li key={schedule.id} className="notifications-item">
                <Link
                  href={`/${currentLocale}/${schedule.ticker}`}
                  className="notifications-item-link"
                >
                  <img
                    className="notifications-item-logo"
                    src={logoUrl(schedule.ticker)}
                    alt=""
                    loading="lazy"
                    onError={(event) => {
                      (event.target as HTMLImageElement).style.display = "none";
                    }}
                  />
                  <span className="notifications-item-ticker">{schedule.ticker}</span>
                  <span
                    className={`notifications-item-status ${
                      isOverdue ? "notifications-item-status-overdue" : ""
                    }`}
                  >
                    {isOverdue ? t("visits.overdue") : t("visits.due_today")}
                  </span>
                  <span className="notifications-item-date">{schedule.next_revisit}</span>
                </Link>
                <button
                  className="notifications-item-dismiss"
                  type="button"
                  aria-label={t("notifications.mark_seen")}
                  title={t("notifications.mark_seen")}
                  onClick={() => dismissReminder.mutate(schedule.id)}
                >
                  ×
                </button>
              </li>
            );
          })}
        </ul>
      )}

      {totalPages > 1 && (
        <div className="notifications-pagination">
          <button
            className="notifications-page-button"
            type="button"
            disabled={page <= 1}
            onClick={() => setPage((previous) => Math.max(1, previous - 1))}
          >
            ← {t("notifications.previous")}
          </button>
          <span className="notifications-page-label">
            {t("notifications.page_of", { current: page, total: totalPages })}
          </span>
          <button
            className="notifications-page-button"
            type="button"
            disabled={page >= totalPages}
            onClick={() => setPage((previous) => Math.min(totalPages, previous + 1))}
          >
            {t("notifications.next")} →
          </button>
        </div>
      )}
    </div>
  );
}
