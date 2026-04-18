"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useAuth } from "../hooks/useAuth";
import { useRevisitSchedules, useVisits } from "../hooks/useVisits";
import { useTranslation } from "../i18n";
import { localToday } from "../utils/format";
import "../styles/revisit-banner.css";

interface RevisitBannerProps {
  ticker: string;
}

const RECURRENCE_OPTIONS = [
  { value: "", labelKey: "visits.recurrence_none" as const },
  { value: "30", labelKey: "visits.recurrence_30d" as const },
  { value: "90", labelKey: "visits.recurrence_90d" as const },
  { value: "182", labelKey: "visits.recurrence_6mo" as const },
  { value: "365", labelKey: "visits.recurrence_1yr" as const },
];

export function RevisitBanner({ ticker }: RevisitBannerProps) {
  const { t } = useTranslation();
  const { isAuthenticated } = useAuth();
  const { getScheduleForTicker, updateSchedule, deleteSchedule } = useRevisitSchedules();
  const { markVisited, isVisitedToday } = useVisits(ticker);
  const expandRef = useRef<HTMLDivElement>(null);

  const [expanded, setExpanded] = useState(false);
  const [expandedMode, setExpandedMode] = useState<"mark" | "settings">("mark");
  const [note, setNote] = useState("");
  const [recurrenceDays, setRecurrenceDays] = useState("");
  const [confirmingCancel, setConfirmingCancel] = useState(false);

  const handleClickOutside = useCallback((event: MouseEvent) => {
    if (expandRef.current && !expandRef.current.contains(event.target as Node)) {
      setExpanded(false);
    }
  }, []);

  const handleEscape = useCallback((event: KeyboardEvent) => {
    if (event.key === "Escape") setExpanded(false);
  }, []);

  useEffect(() => {
    if (!expanded) return;
    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [expanded, handleClickOutside, handleEscape]);

  if (!isAuthenticated) return null;
  if (isVisitedToday(ticker)) return null;

  const schedule = getScheduleForTicker(ticker);
  if (!schedule) return null;

  const today = localToday();
  const isDue = schedule.next_revisit <= today;
  if (!isDue) return null;

  const isOverdue = schedule.next_revisit < today;
  const message = isOverdue
    ? t("visits.banner_overdue", { date: schedule.next_revisit })
    : t("visits.banner_due");

  function handleMarkVisited() {
    setExpandedMode("mark");
    setExpanded(true);
    setNote("");
    setRecurrenceDays(String(schedule!.recurrence_days || ""));
  }

  function handleChangeSettings() {
    setExpandedMode("settings");
    setExpanded(true);
    setRecurrenceDays(String(schedule!.recurrence_days || ""));
    setConfirmingCancel(false);
  }

  function handleSaveMarkVisited() {
    const payload: { ticker: string; note?: string; recurrence_days?: number } = {
      ticker,
    };
    if (note.trim()) payload.note = note.trim();
    if (recurrenceDays) payload.recurrence_days = parseInt(recurrenceDays, 10);

    markVisited.mutate(payload);
    setExpanded(false);
  }

  function handleSaveSettings() {
    updateSchedule.mutate({ id: schedule!.id, recurrence_days: recurrenceDays ? parseInt(recurrenceDays, 10) : null });
    setExpanded(false);
  }

  function handleCancelRecurrence() {
    deleteSchedule.mutate(schedule!.id);
    setExpanded(false);
  }

  return (
    <div className={`revisit-banner ${isOverdue ? "revisit-banner-overdue" : ""}`} ref={expandRef}>
      <div className="revisit-banner-header">
        <span className="revisit-banner-text">{message}</span>
        <div className="revisit-banner-actions">
          <button className="revisit-banner-mark-visited" onClick={handleMarkVisited} type="button">
            {t("visits.mark_visited")}
          </button>
          <button className="revisit-banner-change-settings" onClick={handleChangeSettings} type="button">
            {t("visits.banner_change_settings")}
          </button>
        </div>
      </div>

      {expanded && (
        <div className="revisit-banner-expanded">
          {expandedMode === "mark" && (
            <>
              <textarea
                className="revisit-banner-note-input"
                placeholder={t("visits.add_note")}
                value={note}
                onChange={(event) => setNote(event.target.value)}
                rows={2}
              />
              <label className="revisit-banner-recurrence-label">
                {t("visits.recurrence")}
                <select
                  className="revisit-banner-recurrence-select"
                  value={recurrenceDays}
                  onChange={(event) => setRecurrenceDays(event.target.value)}
                >
                  {RECURRENCE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {t(option.labelKey)}
                    </option>
                  ))}
                </select>
              </label>
              <div className="revisit-banner-actions-footer">
                <button className="revisit-banner-save" onClick={handleSaveMarkVisited} type="button">
                  {t("visits.save")}
                </button>
                <button className="revisit-banner-cancel" onClick={() => setExpanded(false)} type="button">
                  {t("common.cancel")}
                </button>
              </div>
            </>
          )}

          {expandedMode === "settings" && (
            <>
              <label className="revisit-banner-recurrence-label">
                {t("visits.recurrence")}
                <select
                  className="revisit-banner-recurrence-select"
                  value={recurrenceDays}
                  onChange={(event) => setRecurrenceDays(event.target.value)}
                >
                  {RECURRENCE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {t(option.labelKey)}
                    </option>
                  ))}
                </select>
              </label>
              <div className="revisit-banner-actions-footer">
                <button className="revisit-banner-save" onClick={handleSaveSettings} type="button">
                  {t("visits.save")}
                </button>
                {schedule.recurrence_days && !confirmingCancel && (
                  <button
                    className="revisit-banner-cancel-recurrence"
                    onClick={() => setConfirmingCancel(true)}
                    type="button"
                  >
                    {t("visits.banner_cancel_recurrence")}
                  </button>
                )}
                {schedule.recurrence_days && confirmingCancel && (
                  <button
                    className="revisit-banner-cancel-recurrence-confirm"
                    onClick={handleCancelRecurrence}
                    type="button"
                  >
                    {t("visits.banner_cancel_confirm")}
                  </button>
                )}
                <button className="revisit-banner-close" onClick={() => setExpanded(false)} type="button">
                  {t("common.cancel")}
                </button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
