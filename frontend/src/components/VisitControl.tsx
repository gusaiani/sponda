"use client";

import { useEffect, useId, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../hooks/useAuth";
import { useVisits, useRevisitSchedules, type VisitEntry } from "../hooks/useVisits";
import { useTranslation } from "../i18n";
import { AuthModal } from "./AuthModal";
import { LocalizedDateInput } from "./LocalizedDateInput";
import { formatCalendarDate, localToday } from "../utils/format";
import { consumePendingAuthAction, type PendingAuthAction } from "../utils/postLoginReturn";
import "../styles/visit-control.css";

interface VisitControlProps {
  ticker: string;
}

type VisitState = "unvisited" | "today" | "earlier";

const RECURRENCE_OPTIONS = [
  { value: "", labelKey: "visits.recurrence_none" as const },
  { value: "30", labelKey: "visits.recurrence_30d" as const },
  { value: "90", labelKey: "visits.recurrence_90d" as const },
  { value: "182", labelKey: "visits.recurrence_6mo" as const },
  { value: "365", labelKey: "visits.recurrence_1yr" as const },
];

function newestFirst(visits: VisitEntry[]): VisitEntry[] {
  return [...visits].sort((first, second) => second.visited_at.localeCompare(first.visited_at));
}

/**
 * The company header's visit control: one capsule beside the favorite star
 * that says where the visitor stands with this company (never visited,
 * visited today, last visited on a date) and opens a panel with the action,
 * the note and revisit schedule, and every past visit.
 */
export function VisitControl({ ticker }: VisitControlProps) {
  const { t, locale } = useTranslation();
  const { isAuthenticated } = useAuth();
  const { visits, isVisitedToday, markVisited } = useVisits(ticker);
  const { getScheduleForTicker } = useRevisitSchedules();
  const queryClient = useQueryClient();
  const controlRef = useRef<HTMLDivElement>(null);
  const popoverId = useId();

  const [open, setOpen] = useState(false);
  const [markedThisSession, setMarkedThisSession] = useState(false);
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [note, setNote] = useState("");
  const [nextRevisit, setNextRevisit] = useState("");
  const [recurrenceDays, setRecurrenceDays] = useState("");

  const sortedVisits = newestFirst(visits);
  const latestVisit = sortedVisits[0];
  // The visit just marked counts before the refetched list confirms it.
  const visitedToday = isAuthenticated && (markedThisSession || isVisitedToday(ticker));
  const visitState: VisitState = visitedToday
    ? "today"
    : isAuthenticated && latestVisit
      ? "earlier"
      : "unvisited";
  const markVisitedAction: PendingAuthAction = { kind: "mark-visited", ticker };

  const capsuleLabel = {
    unvisited: t("visits.mark_visited"),
    today: t("visits.visited_today"),
    earlier: latestVisit
      ? t("visits.last_visit", { date: formatCalendarDate(latestVisit.visited_at, locale) })
      : "",
  }[visitState];

  function markToday() {
    markVisited.mutate({ ticker });
    setMarkedThisSession(true);
  }

  function markTodayAndOpen() {
    markToday();
    setOpen(true);
  }

  // Resume a "mark as visited" that sent the visitor through Google login.
  // sessionStorage is outside React, so the effect is the sync point.
  useEffect(() => {
    if (!isAuthenticated) return;
    if (!consumePendingAuthAction({ kind: "mark-visited", ticker })) return;
    markVisited.mutate({ ticker });
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMarkedThisSession(true);
    setOpen(true);
  }, [isAuthenticated, ticker, markVisited]);

  useEffect(() => {
    if (!open) return;
    function handleClickOutside(event: MouseEvent) {
      if (controlRef.current && !controlRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [open]);

  function handleCapsuleClick() {
    if (!isAuthenticated) {
      setShowAuthModal(true);
      return;
    }
    if (visitState === "unvisited") {
      markTodayAndOpen();
      return;
    }
    setOpen(!open);
  }

  function handleAuthSuccess() {
    setShowAuthModal(false);
    consumePendingAuthAction(markVisitedAction);
    queryClient.invalidateQueries({ queryKey: ["auth-user"] }).then(markTodayAndOpen);
  }

  function handleSave() {
    const payload: { ticker: string; note?: string; next_revisit?: string; recurrence_days?: number } = {
      ticker,
    };
    if (note.trim()) payload.note = note.trim();
    if (nextRevisit) payload.next_revisit = nextRevisit;
    if (recurrenceDays) payload.recurrence_days = parseInt(recurrenceDays, 10);

    markVisited.mutate(payload);
    setOpen(false);
    setNote("");
    setNextRevisit("");
    setRecurrenceDays("");
  }

  const schedule = isAuthenticated ? getScheduleForTicker(ticker) : undefined;
  const scheduleRecurrence = RECURRENCE_OPTIONS.find(
    (option) => option.value !== "" && option.value === String(schedule?.recurrence_days),
  );

  return (
    <div className="visit-control" ref={controlRef}>
      <button
        type="button"
        className={`visit-control-capsule visit-control-capsule--${visitState}`}
        onClick={handleCapsuleClick}
        aria-label={capsuleLabel}
        title={capsuleLabel}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={open ? popoverId : undefined}
      >
        <VisitIcon filled={visitState === "today"} />
        <span className="visit-control-label">{capsuleLabel}</span>
        {visitState !== "unvisited" && <ChevronIcon />}
      </button>

      {open && isAuthenticated && (
        <div id={popoverId} className="visit-control-popover" role="dialog" aria-label={t("visits.history")}>
          {schedule && (
            <p className="visit-control-schedule">
              {t("visits.next_revisit")} <strong>{formatCalendarDate(schedule.next_revisit, locale)}</strong>
              {scheduleRecurrence && <> · {t(scheduleRecurrence.labelKey)}</>}
            </p>
          )}

          {visitedToday ? (
            <div className="visit-control-form">
              <textarea
                className="visit-control-note"
                placeholder={t("visits.add_note")}
                value={note}
                onChange={(event) => setNote(event.target.value)}
                rows={2}
              />
              <div className="visit-control-fields">
                <label className="visit-control-field">
                  {t("visits.next_revisit")}
                  <LocalizedDateInput
                    className="visit-control-input visit-control-date"
                    value={nextRevisit}
                    onChange={setNextRevisit}
                    min={localToday()}
                  />
                </label>
                <label className="visit-control-field">
                  {t("visits.recurrence")}
                  <select
                    className="visit-control-input visit-control-recurrence"
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
              </div>
              <button type="button" className="visit-control-primary" onClick={handleSave}>
                {t("visits.save")}
              </button>
            </div>
          ) : (
            <button type="button" className="visit-control-primary" onClick={markToday}>
              {t("visits.mark_visited_today")}
            </button>
          )}

          {sortedVisits.length > 0 && (
            <section className="visit-control-history">
              <h3 className="visit-control-history-heading">
                {t("visits.history")}
                <span className="visit-control-history-count">{sortedVisits.length}</span>
              </h3>
              <ol className="visit-control-history-list">
                {sortedVisits.map((visit) => (
                  <li key={visit.id} className="visit-control-history-item">
                    <span className="visit-control-history-date">
                      {formatCalendarDate(visit.visited_at, locale)}
                    </span>
                    {visit.note.trim() && <span className="visit-control-history-note">{visit.note}</span>}
                  </li>
                ))}
              </ol>
            </section>
          )}
        </div>
      )}

      {showAuthModal && (
        <AuthModal
          onSuccess={handleAuthSuccess}
          onClose={() => setShowAuthModal(false)}
          message={t("visits.must_login")}
          pendingAction={markVisitedAction}
        />
      )}
    </div>
  );
}

function VisitIcon({ filled }: { filled: boolean }) {
  return (
    <svg className="visit-control-icon" width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
      <circle
        cx="12"
        cy="12"
        r="9.5"
        fill={filled ? "currentColor" : "none"}
        stroke="currentColor"
        strokeWidth="1.75"
      />
      <polyline
        points="8 12.5 11 15.5 16.5 9.5"
        fill="none"
        stroke={filled ? "#ffffff" : "currentColor"}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function ChevronIcon() {
  return (
    <svg className="visit-control-chevron" width="10" height="10" viewBox="0 0 24 24" aria-hidden="true">
      <polyline
        points="6 9 12 15 18 9"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
