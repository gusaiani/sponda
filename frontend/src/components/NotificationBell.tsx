"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { useAuth } from "../hooks/useAuth";
import { usePendingReminders } from "../hooks/useVisits";
import { useTranslation } from "../i18n";
import "../styles/notification-bell.css";

export function NotificationBell() {
  const { isAuthenticated } = useAuth();
  const { count, schedules } = usePendingReminders();
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

  if (!isAuthenticated || count === 0) return null;

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
        <span className="notification-bell-badge">{count}</span>
      </button>

      {isOpen && (
        <div className="notification-bell-menu">
          <div className="notification-bell-header">{t("notifications.title")}</div>
          {schedules.map((schedule) => {
            const today = new Date().toISOString().slice(0, 10);
            const isOverdue = schedule.next_revisit < today;
            return (
              <Link
                key={schedule.id}
                href={`/${locale}/${schedule.ticker}`}
                className="notification-bell-item"
                onClick={() => setIsOpen(false)}
              >
                <span className="notification-bell-ticker">{schedule.ticker}</span>
                <span className={`notification-bell-status ${isOverdue ? "notification-bell-status-overdue" : ""}`}>
                  {isOverdue ? t("visits.overdue") : t("visits.due_today")}
                </span>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
