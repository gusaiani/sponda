"use client";

import { useRef, useState } from "react";
import { useTranslation } from "../i18n";
import { formatCalendarDate } from "../utils/format";
import {
  DIGITS_IN_FULL_DATE,
  dateFieldLayout,
  maskDateDigits,
  parseLocalizedDate,
  type DatePart,
} from "../utils/localizedDate";
import "../styles/localized-date-input.css";

interface LocalizedDateInputProps {
  /** ISO date ("YYYY-MM-DD"), or "" for none. */
  value: string;
  onChange: (isoDate: string) => void;
  /** Earliest accepted ISO date. */
  min?: string;
  className?: string;
  id?: string;
}

/**
 * A date field in the site's language rather than the browser's. A native
 * `<input type="date">` draws its placeholder from the browser locale, so a
 * French browser showed "jj/mm/aaaa" on the Portuguese site. This field
 * shows the active locale's placeholder and order, and still offers the
 * browser's calendar through a button.
 */
export function LocalizedDateInput({ value, onChange, min, className = "", id }: LocalizedDateInputProps) {
  const { t, locale } = useTranslation();
  const pickerRef = useRef<HTMLInputElement>(null);
  const [draft, setDraft] = useState(() => (value ? formatCalendarDate(value, locale) : ""));

  const { order, separator } = dateFieldLayout(locale);
  const placeholderPart: Record<DatePart, string> = {
    day: t("dates.day_placeholder"),
    month: t("dates.month_placeholder"),
    year: t("dates.year_placeholder"),
  };
  const placeholder = order.map((part) => placeholderPart[part]).join(separator);

  function acceptedDate(text: string): string {
    const isoDate = parseLocalizedDate(text, locale);
    const isAllowed = isoDate !== null && (min === undefined || isoDate >= min);
    return isAllowed ? isoDate : "";
  }

  // Show what the visitor typed while it agrees with the value (a rejected
  // or partial entry agrees with ""). When the value changes from outside
  // (calendar, reset after saving), show the value instead.
  const draftDate = acceptedDate(draft);
  const isShowingDraft = draftDate === value;
  const text = isShowingDraft ? draft : value ? formatCalendarDate(value, locale) : "";
  const isComplete = text.replace(/\D/g, "").length === DIGITS_IN_FULL_DATE;
  const isInvalid = isShowingDraft && isComplete && draftDate === "";

  function handleTyping(rawText: string) {
    const masked = maskDateDigits(rawText, locale);
    setDraft(masked);
    onChange(acceptedDate(masked));
  }

  function handleCalendarPick(isoDate: string) {
    const formatted = isoDate ? formatCalendarDate(isoDate, locale) : "";
    setDraft(formatted);
    onChange(acceptedDate(formatted));
  }

  function openCalendar() {
    const picker = pickerRef.current;
    if (!picker) return;
    try {
      picker.showPicker();
    } catch {
      picker.focus();
    }
  }

  return (
    <span className="localized-date-input">
      <input
        id={id}
        type="text"
        inputMode="numeric"
        autoComplete="off"
        className={`localized-date-input-text ${className}`}
        placeholder={placeholder}
        value={text}
        maxLength={10}
        aria-invalid={isInvalid}
        onChange={(event) => handleTyping(event.target.value)}
      />
      <button
        type="button"
        className="localized-date-input-calendar"
        aria-label={t("dates.open_calendar")}
        title={t("dates.open_calendar")}
        onClick={openCalendar}
      >
        <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
          <rect x="3.5" y="5" width="17" height="15.5" rx="2.5" fill="none" stroke="currentColor" strokeWidth="1.75" />
          <line x1="3.5" y1="10" x2="20.5" y2="10" stroke="currentColor" strokeWidth="1.75" />
          <line x1="8" y1="3" x2="8" y2="7" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
          <line x1="16" y1="3" x2="16" y2="7" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
        </svg>
      </button>
      <input
        ref={pickerRef}
        type="date"
        className="localized-date-input-picker"
        tabIndex={-1}
        aria-hidden="true"
        value={value}
        min={min}
        onChange={(event) => handleCalendarPick(event.target.value)}
      />
    </span>
  );
}
