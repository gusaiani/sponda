"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { useAuth } from "../hooks/useAuth";
import { useAlertNotifications } from "../hooks/useAlertNotifications";
import { usePendingReminders } from "../hooks/useVisits";
import { useTranslation } from "../i18n";
import { localToday, logoUrl } from "../utils/format";
import "../styles/notification-bell.css";

const ALERT_INDICATOR_LABELS: Record<string, string> = {
  current_price: "Price",
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

const CURRENCY_INDICATORS = new Set(["current_price", "market_cap"]);
const RATIO_INDICATORS = new Set([
  "pe10", "pfcf10", "peg", "pfcf_peg",
  "debt_to_equity", "debt_ex_lease_to_equity", "liabilities_to_equity",
  "current_ratio", "debt_to_avg_earnings", "debt_to_avg_fcf",
]);

function formatAlertValue(indicator: string, value: string): string {
  const number = parseFloat(value);
  if (isNaN(number)) return value;
  if (CURRENCY_INDICATORS.has(indicator)) return `R$ ${number.toFixed(2)}`;
  if (RATIO_INDICATORS.has(indicator)) return `${number.toFixed(2)}×`;
  return number.toFixed(2);
}

const DROPDOWN_LIMIT = 10;

export function NotificationBell() {
  const { isAuthenticated } = useAuth();
  const {
    count: alertCount,
    notifications: alertNotifications,
    dismissNotification,
    dismissAllNotifications,
  } = useAlertNotifications();
  const { count: reminderCount, schedules, dismissReminder, dismissAllReminders } =
    usePendingReminders();
  const { t, locale } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    if (isOpen) document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isOpen]);

  const totalCount = alertCount + reminderCount;

  if (!isAuthenticated || totalCount === 0) return null;

  const hasMore = totalCount > DROPDOWN_LIMIT;

  function handleDismissAll() {
    if (alertCount > 0) dismissAllNotifications.mutate();
    if (reminderCount > 0) dismissAllReminders.mutate();
  }

  return (
    <div className="notification-bell" ref={menuRef}>
      <button
        className="notification-bell-trigger"
        onClick={() => setIsOpen(!isOpen)}
        aria-label={t("notifications.title")}
        type="button"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
          <path d="M13.73 21a2 2 0 0 1-3.46 0" />
        </svg>
        <span className="notification-bell-badge">{totalCount}</span>
      </button>

      {isOpen && (
        <div className="notification-bell-menu">
          <div className="notification-bell-header-row">
            <span className="notification-bell-header">{t("notifications.title")}</span>
            <button
              className="notification-bell-mark-all"
              type="button"
              onClick={handleDismissAll}
              disabled={dismissAllNotifications.isPending || dismissAllReminders.isPending}
            >
              {t("notifications.mark_all_seen")}
            </button>
          </div>

          {alertNotifications.map((notification) => {
            const indicatorLabel =
              ALERT_INDICATOR_LABELS[notification.indicator] ?? notification.indicator;
            const operator = notification.comparison === "lte" ? "≤" : "≥";
            return (
              <div key={`alert-${notification.id}`} className="notification-bell-item">
                <Link
                  href={`/${locale}/${notification.ticker}`}
                  className="notification-bell-item-link"
                  onClick={() => setIsOpen(false)}
                >
                  <span className="notification-bell-ticker">{notification.ticker}</span>
                  <span className="notification-bell-status notification-bell-status-overdue">
                    {t("notifications.triggered_alert_text", {
                      indicator: indicatorLabel,
                      operator,
                      threshold: formatAlertValue(notification.indicator, notification.threshold),
                    })}
                  </span>
                </Link>
                <button
                  className="notification-bell-dismiss"
                  type="button"
                  aria-label={t("notifications.mark_seen")}
                  title={t("notifications.mark_seen")}
                  onClick={(event) => {
                    event.stopPropagation();
                    dismissNotification.mutate(notification.id);
                  }}
                >
                  ×
                </button>
              </div>
            );
          })}

          {schedules.map((schedule) => {
            const today = localToday();
            const isOverdue = schedule.next_revisit < today;
            return (
              <div key={`reminder-${schedule.id}`} className="notification-bell-item">
                <Link
                  href={`/${locale}/${schedule.ticker}`}
                  className="notification-bell-item-link"
                  onClick={() => setIsOpen(false)}
                >
                  <span className="notification-bell-ticker">{schedule.ticker}</span>
                  <span className={`notification-bell-status ${isOverdue ? "notification-bell-status-overdue" : ""}`}>
                    {isOverdue ? t("visits.overdue") : t("visits.due_today")}
                  </span>
                </Link>
                <button
                  className="notification-bell-dismiss"
                  type="button"
                  aria-label={t("notifications.mark_seen")}
                  title={t("notifications.mark_seen")}
                  onClick={(event) => {
                    event.stopPropagation();
                    dismissReminder.mutate(schedule.id);
                  }}
                >
                  ×
                </button>
              </div>
            );
          })}
          {hasMore && (
            <Link
              href={`/${locale}/notificacoes`}
              className="notification-bell-see-all"
              onClick={() => setIsOpen(false)}
            >
              {t("notifications.see_all", { count: totalCount })}
            </Link>
          )}
        </div>
      )}
    </div>
  );
}
