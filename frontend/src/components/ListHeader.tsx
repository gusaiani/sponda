"use client";

import { useTranslation } from "../i18n";
import "../styles/list-header.css";

interface ListHeaderProps {
  name: string;
  tickerCount: number;
  years: number;
}

/**
 * The identity of a saved list, standing in for the company header.
 *
 * A list is opened at one of its members' URLs because that is where the
 * comparison table lives, but the list is not about that company: it
 * outlives the company being removed from it, and naming the company here
 * made the list look like a property of whichever member happened to be
 * first. This header names the list and nothing else.
 */
export function ListHeader({ name, tickerCount, years }: ListHeaderProps) {
  const { t, pluralize } = useTranslation();

  return (
    <div className="list-header">
      <h2 className="list-header-name">{name}</h2>
      <p className="list-header-meta">
        {tickerCount} {t("common.companies")} ·{" "}
        {years} {pluralize(years, "common.year_singular", "common.year_plural")}
      </p>
    </div>
  );
}
