"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { useAuth } from "../hooks/useAuth";
import { useAlertNotifications } from "../hooks/useAlertNotifications";
import { usePendingReminders } from "../hooks/useVisits";
import { useFollowRequestAction } from "../hooks/useFollow";
import {
  useMarkNotificationsRead,
  useSocialNotifications,
  type SocialNotification,
} from "../hooks/useSocialNotifications";
import { UserAvatar } from "./social/UserAvatar";
import { useTranslation } from "../i18n";
import type { TranslationKey } from "../i18n/types";
import { localToday } from "../utils/format";
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

const SOCIAL_LIMIT = 8;

/**
 * Unified notification bell — surfaces alerts, scheduled revisits, and
 * social activity (replies, mentions, likes, follows, follow requests)
 * in a single dropdown with three sections.
 */
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
  const socialQuery = useSocialNotifications(isAuthenticated);
  const markSocialRead = useMarkNotificationsRead();
  const followRequestAction = useFollowRequestAction();
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

  const socialUnread = socialQuery.data?.unread_count ?? 0;
  const socialItems = (socialQuery.data?.notifications ?? []).slice(0, SOCIAL_LIMIT);
  const totalCount = alertCount + reminderCount + socialUnread;

  if (!isAuthenticated || totalCount === 0) return null;

  function handleDismissAll() {
    if (alertCount > 0) dismissAllNotifications.mutate();
    if (reminderCount > 0) dismissAllReminders.mutate();
    if (socialUnread > 0) markSocialRead.mutate(undefined);
  }

  return (
    <div className="notification-bell" ref={menuRef}>
      <button
        className="notification-bell-trigger"
        onClick={() => setIsOpen(!isOpen)}
        aria-label={t("notifications.title")}
        type="button"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
          <path d="M13.73 21a2 2 0 0 1-3.46 0" />
        </svg>
        <span className="notification-bell-badge">{totalCount > 99 ? "99+" : totalCount}</span>
      </button>

      {isOpen && (
        <div className="notification-bell-menu">
          <div className="notification-bell-header-row">
            <span className="notification-bell-header">{t("notifications.title")}</span>
            <button
              className="notification-bell-mark-all"
              type="button"
              onClick={handleDismissAll}
              disabled={
                dismissAllNotifications.isPending
                || dismissAllReminders.isPending
                || markSocialRead.isPending
              }
            >
              {t("notifications.mark_all_seen")}
            </button>
          </div>

          {socialItems.length > 0 && (
            <>
              <div className="notification-bell-section-label">{t("social.spond_noun_plural")}</div>
              {socialItems.map((notification) => (
                <SocialRow
                  key={`social-${notification.id}`}
                  notification={notification}
                  locale={locale}
                  t={t}
                  onClose={() => setIsOpen(false)}
                  onAccept={(id) => followRequestAction.mutate({ id, action: "accept" })}
                  onReject={(id) => followRequestAction.mutate({ id, action: "reject" })}
                />
              ))}
            </>
          )}

          {alertNotifications.length > 0 && (
            <>
              <div className="notification-bell-section-label">{t("alerts.page_title")}</div>
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
            </>
          )}

          {schedules.length > 0 && (
            <>
              <div className="notification-bell-section-label">{t("visits.page_title")}</div>
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
            </>
          )}
        </div>
      )}
    </div>
  );
}

interface SocialRowProps {
  notification: SocialNotification;
  locale: string;
  t: (key: TranslationKey, params?: Record<string, string | number>) => string;
  onClose: () => void;
  onAccept: (id: number) => void;
  onReject: (id: number) => void;
}

function SocialRow({ notification, locale, t, onClose, onAccept, onReject }: SocialRowProps) {
  const actor = notification.actor;
  const actorName = actor?.display_name || (actor?.handle ? `@${actor.handle}` : "");
  const verbKey: TranslationKey =
    notification.verb === "followed" ? "social.notifications.followed"
      : notification.verb === "follow_requested" ? "social.notifications.follow_requested"
      : notification.verb === "replied" ? "social.notifications.replied"
      : notification.verb === "mentioned" ? "social.notifications.mentioned"
      : "social.notifications.liked";

  const targetHref =
    notification.target_type === "spond" && notification.target_id
      ? `/${locale}/spond/${notification.target_id}`
      : notification.target_type === "follow" && actor
        ? `/${locale}/user/${actor.handle}`
        : null;

  const body = (
    <div className="notification-bell-social-row">
      {actor && (
        <UserAvatar handle={actor.handle} displayName={actor.display_name} size="sm" />
      )}
      <div className="notification-bell-social-text">
        <span>{t(verbKey, { actor: actorName })}</span>
        {notification.verb === "follow_requested" && (
          <div className="notification-bell-social-actions">
            <button
              type="button"
              className="notification-bell-social-accept"
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                onAccept(Number(notification.target_id));
              }}
            >
              {t("social.notifications.accept")}
            </button>
            <button
              type="button"
              className="notification-bell-social-reject"
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                onReject(Number(notification.target_id));
              }}
            >
              {t("social.notifications.reject")}
            </button>
          </div>
        )}
      </div>
    </div>
  );

  return (
    <div className={`notification-bell-item${notification.read_at ? "" : " notification-bell-item--unread"}`}>
      {targetHref ? (
        <Link href={targetHref} className="notification-bell-item-link" onClick={onClose}>
          {body}
        </Link>
      ) : (
        <div className="notification-bell-item-link">{body}</div>
      )}
    </div>
  );
}
