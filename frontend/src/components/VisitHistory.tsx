"use client";

import { useId, useState } from "react";
import { useAuth } from "../hooks/useAuth";
import { useVisits, type VisitEntry } from "../hooks/useVisits";
import { useTranslation } from "../i18n";
import { formatCalendarDate } from "../utils/format";
import "../styles/visit-history.css";

interface VisitHistoryProps {
  ticker: string;
}

function newestFirst(visits: VisitEntry[]): VisitEntry[] {
  return [...visits].sort((first, second) => second.visited_at.localeCompare(first.visited_at));
}

/**
 * "Last visit on <date>" under the company header, with an in-place toggle
 * that lists every visit to this company and its note.
 */
export function VisitHistory({ ticker }: VisitHistoryProps) {
  const { t, locale } = useTranslation();
  const { isAuthenticated } = useAuth();
  const { visits } = useVisits(ticker);
  const [expanded, setExpanded] = useState(false);
  const listId = useId();

  if (!isAuthenticated || visits.length === 0) return null;

  const sortedVisits = newestFirst(visits);
  const latestVisit = sortedVisits[0];
  const hasMoreToShow = sortedVisits.length > 1 || latestVisit.note.trim() !== "";

  return (
    <div className="visit-history">
      <div className="visit-history-summary">
        <span className="visit-history-latest">
          {t("visits.last_visit", { date: formatCalendarDate(latestVisit.visited_at, locale) })}
        </span>
        {hasMoreToShow && (
          <button
            type="button"
            className="visit-history-toggle"
            aria-expanded={expanded}
            aria-controls={listId}
            onClick={() => setExpanded(!expanded)}
          >
            {expanded ? t("visits.hide_all") : t("visits.show_all", { count: sortedVisits.length })}
          </button>
        )}
      </div>

      {expanded && (
        <ol id={listId} className="visit-history-list">
          {sortedVisits.map((visit) => (
            <li key={visit.id} className="visit-history-item">
              <span className="visit-history-date">{formatCalendarDate(visit.visited_at, locale)}</span>
              {visit.note.trim() && <span className="visit-history-note">{visit.note}</span>}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
