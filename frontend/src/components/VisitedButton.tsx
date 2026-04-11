"use client";

import { useState, useRef, useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../hooks/useAuth";
import { useVisits } from "../hooks/useVisits";
import { useTranslation } from "../i18n";
import { AuthModal } from "./AuthModal";
import "../styles/visited-button.css";

interface VisitedButtonProps {
  ticker: string;
}

const RECURRENCE_OPTIONS = [
  { value: "", labelKey: "visits.recurrence_none" as const },
  { value: "30", labelKey: "visits.recurrence_30d" as const },
  { value: "90", labelKey: "visits.recurrence_90d" as const },
  { value: "182", labelKey: "visits.recurrence_6mo" as const },
  { value: "365", labelKey: "visits.recurrence_1yr" as const },
];

export function VisitedButton({ ticker }: VisitedButtonProps) {
  const { t } = useTranslation();
  const { isAuthenticated } = useAuth();
  const { visits, isVisitedToday, markVisited } = useVisits();
  const queryClient = useQueryClient();
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [note, setNote] = useState("");
  const [nextRevisit, setNextRevisit] = useState("");
  const [recurrenceDays, setRecurrenceDays] = useState("");
  const expandRef = useRef<HTMLDivElement>(null);

  const visited = isAuthenticated && isVisitedToday(ticker);
  const visitCount = visits.filter((visit) => visit.ticker === ticker.toUpperCase()).length;
  const showProminent = !visited && (!isAuthenticated || visitCount < 3);

  // Close on click outside
  useEffect(() => {
    if (!expanded) return;
    function handleClickOutside(event: MouseEvent) {
      if (expandRef.current && !expandRef.current.contains(event.target as Node)) {
        setExpanded(false);
      }
    }
    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setExpanded(false);
    }
    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [expanded]);

  function handleClick() {
    if (!isAuthenticated) {
      setShowAuthModal(true);
      return;
    }
    if (!visited) {
      markVisited.mutate({ ticker });
    }
    setExpanded(!expanded);
  }

  function handleSave() {
    const payload: { ticker: string; note?: string; next_revisit?: string; recurrence_days?: number } = {
      ticker,
    };
    if (note.trim()) payload.note = note.trim();
    if (nextRevisit) payload.next_revisit = nextRevisit;
    if (recurrenceDays) payload.recurrence_days = parseInt(recurrenceDays, 10);

    markVisited.mutate(payload);
    setExpanded(false);
    setNote("");
    setNextRevisit("");
    setRecurrenceDays("");
  }

  function handleAuthSuccess() {
    setShowAuthModal(false);
    queryClient.invalidateQueries({ queryKey: ["auth-user"] }).then(() => {
      markVisited.mutate({ ticker });
    });
  }

  if (showProminent) {
    return (
      <>
        <button
          className="visited-button-prominent"
          onClick={handleClick}
          aria-label={t("visits.mark_visited")}
          title={t("visits.mark_visited")}
          type="button"
        >
          <svg className="visited-button-prominent-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="20 6 9 17 4 12" />
          </svg>
          <span className="visited-button-prominent-label">{t("visits.mark_visited")}</span>
        </button>

        {showAuthModal && (
          <AuthModal
            onSuccess={handleAuthSuccess}
            onClose={() => setShowAuthModal(false)}
            message={t("visits.must_login")}
          />
        )}
      </>
    );
  }

  return (
    <>
      <div className="visited-button-wrapper" ref={expandRef}>
        <button
          className={`visited-button ${visited ? "visited-button-active" : ""}`}
          onClick={handleClick}
          aria-label={visited ? t("visits.visited_today") : t("visits.mark_visited")}
          title={visited ? t("visits.visited_today") : t("visits.mark_visited")}
          type="button"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="20 6 9 17 4 12" />
          </svg>
        </button>

        {expanded && isAuthenticated && (
          <div className="visited-expand">
            <textarea
              className="visited-note-input"
              placeholder={t("visits.add_note")}
              value={note}
              onChange={(event) => setNote(event.target.value)}
              rows={2}
            />
            <div className="visited-schedule-row">
              <label className="visited-schedule-label">
                {t("visits.next_revisit")}
                <input
                  type="date"
                  className="visited-date-input"
                  value={nextRevisit}
                  onChange={(event) => setNextRevisit(event.target.value)}
                  min={new Date().toISOString().slice(0, 10)}
                />
              </label>
              <label className="visited-schedule-label">
                {t("visits.recurrence")}
                <select
                  className="visited-recurrence-select"
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
            <button className="visited-save-button" onClick={handleSave} type="button">
              {t("visits.save")}
            </button>
          </div>
        )}
      </div>

      {showAuthModal && (
        <AuthModal
          onSuccess={handleAuthSuccess}
          onClose={() => setShowAuthModal(false)}
          message={t("visits.must_login")}
        />
      )}
    </>
  );
}
