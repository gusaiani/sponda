"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useAuth } from "../../../hooks/useAuth";
import { usePendingReminders, useRemindersList } from "../../../hooks/useVisits";
import { useAlerts } from "../../../hooks/useAlerts";
import { useTranslation } from "../../../i18n";
import { localToday, logoUrl } from "../../../utils/format";
import "../../../styles/notifications-page.css";

/**
 * Human-readable labels for each alert-capable indicator.
 * Mirrors INDICATOR_LABELS on the screener page — kept local (not shared) so
 * the two pages can diverge as needed without breaking each other.
 */
const ALERT_INDICATOR_LABELS: Record<string, string> = {
  pe10: "PE10",
  pfcf10: "PFCF10",
  peg: "PEG",
  pfcf_peg: "P/FCF PEG",
  debt_to_equity: "Debt / Equity",
  debt_ex_lease_to_equity: "Debt (ex-lease) / Eq.",
  liabilities_to_equity: "Liab / Equity",
  current_ratio: "Current Ratio",
  debt_to_avg_earnings: "Debt / Avg Earnings",
  debt_to_avg_fcf: "Debt / Avg FCF",
  market_cap: "Market Cap",
};

const PAGE_SIZE = 30;

export default function NotificationsPage() {
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const { t, locale } = useTranslation();
  const params = useParams<{ locale: string }>();
  const currentLocale = params.locale || locale;
  const [page, setPage] = useState(1);
  const { data, isLoading } = useRemindersList(page);
  const { dismissReminder, dismissAllReminders } = usePendingReminders();
  const { alerts, deleteAlert } = useAlerts();
  const triggeredAlerts = alerts.filter((alert) => alert.triggered_at !== null);

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

      <section className="notifications-section">
        <h2 className="notifications-section-title">
          {t("notifications.triggered_alerts_title")}
        </h2>
        {triggeredAlerts.length === 0 ? (
          <p className="notifications-empty">{t("notifications.no_triggered_alerts")}</p>
        ) : (
          <ul className="notifications-list">
            {triggeredAlerts.map((alert) => {
              const indicatorLabel =
                ALERT_INDICATOR_LABELS[alert.indicator] ?? alert.indicator;
              const operator = alert.comparison === "lte" ? "≤" : "≥";
              return (
                <li key={alert.id} className="notifications-item">
                  <Link
                    href={`/${currentLocale}/${alert.ticker}`}
                    className="notifications-item-link"
                  >
                    <img
                      className="notifications-item-logo"
                      src={logoUrl(alert.ticker)}
                      alt=""
                      loading="lazy"
                      onError={(event) => {
                        (event.target as HTMLImageElement).style.display = "none";
                      }}
                    />
                    <span className="notifications-item-ticker">{alert.ticker}</span>
                    <span className="notifications-item-status notifications-item-status-overdue">
                      {t("notifications.triggered_alert_text", {
                        indicator: indicatorLabel,
                        operator,
                        threshold: alert.threshold,
                      })}
                    </span>
                  </Link>
                  <button
                    className="notifications-item-dismiss"
                    type="button"
                    aria-label={t("alerts.delete")}
                    title={t("alerts.delete")}
                    onClick={() => deleteAlert.mutate(alert.id)}
                  >
                    ×
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <section className="notifications-section">
        <h2 className="notifications-section-title">
          {t("notifications.revisits_title")}
        </h2>
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
      </section>
    </div>
  );
}
