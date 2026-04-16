"use client";

import { useCallback, useRef, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  useScreener,
  SCREENER_INDICATORS,
  ScreenerFilters,
  ScreenerIndicator,
} from "../../../hooks/useScreener";
import { useInfiniteScrollTrigger } from "../../../hooks/useInfiniteScrollTrigger";
import { useTranslation } from "../../../i18n";
import { formatLargeNumber, logoUrl, br } from "../../../utils/format";
import "../../../styles/screener.css";

const PAGE_SIZE = 20;

/** Human-readable labels for each indicator, shown in the filter sidebar
 * and as table column headers. Kept here (rather than in a shared util)
 * because the screener is currently the only consumer. */
const INDICATOR_LABELS: Record<ScreenerIndicator, string> = {
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

/** Display the 'market_cap' column as a formatted currency; other
 * indicator columns are plain decimals. */
function formatIndicatorValue(
  indicator: ScreenerIndicator,
  rawValue: string | number | null,
  ticker: string,
): string {
  if (rawValue === null || rawValue === undefined || rawValue === "") return "—";
  const value = typeof rawValue === "string" ? Number(rawValue) : rawValue;
  if (Number.isNaN(value)) return "—";
  if (indicator === "market_cap") {
    return formatLargeNumber(value, ticker);
  }
  return br(value, 2);
}

function emptyBounds(): ScreenerFilters["bounds"] {
  return {};
}

export default function ScreenerPage() {
  const { t } = useTranslation();
  const params = useParams<{ locale: string }>();
  const locale = params?.locale || "pt";

  const [draftBounds, setDraftBounds] = useState<ScreenerFilters["bounds"]>(emptyBounds);
  const [appliedFilters, setAppliedFilters] = useState<ScreenerFilters>({
    bounds: {},
    sort: "market_cap",
    limit: PAGE_SIZE,
    offset: 0,
  });

  const { data, isLoading, isFetching } = useScreener(appliedFilters);
  const rows = data?.results ?? [];
  const totalCount = data?.count ?? 0;
  const hasMore = rows.length < totalCount;
  const sentinelRef = useRef<HTMLDivElement | null>(null);

  function handleBoundChange(
    indicator: ScreenerIndicator,
    side: "min" | "max",
    value: string,
  ) {
    setDraftBounds((previous) => ({
      ...previous,
      [indicator]: { ...previous[indicator], [side]: value },
    }));
  }

  function applyFilters() {
    setAppliedFilters((previous) => ({
      ...previous,
      bounds: draftBounds,
      offset: 0,
    }));
  }

  function clearFilters() {
    setDraftBounds(emptyBounds());
    setAppliedFilters((previous) => ({
      ...previous,
      bounds: {},
      offset: 0,
    }));
  }

  function toggleSort(field: string) {
    setAppliedFilters((previous) => {
      const currentlyDescendingOnField = previous.sort === `-${field}`;
      const nextSort = currentlyDescendingOnField ? field : `-${field}`;
      return { ...previous, sort: nextSort, offset: 0 };
    });
  }

  const loadMore = useCallback(() => {
    setAppliedFilters((previous) => ({
      ...previous,
      limit: previous.limit + PAGE_SIZE,
    }));
  }, []);

  useInfiniteScrollTrigger({
    ref: sentinelRef,
    onVisible: loadMore,
    enabled: hasMore && !isFetching,
  });

  return (
    <div className="screener-page">
      <Link href={`/${locale}`} className="auth-logo-link">
        <span className="auth-logo">SPONDA</span>
      </Link>
      <div className="screener-header">
        <h1 className="screener-title">{t("screener.page_title")}</h1>
        <p className="screener-hint">{t("screener.page_hint")}</p>
      </div>

      <div className="screener-layout">
        <aside className="screener-filters" aria-label={t("screener.filters_title")}>
          <h2 className="screener-filters-title">{t("screener.filters_title")}</h2>
          {SCREENER_INDICATORS.map((indicator) => {
            const bound = draftBounds[indicator] ?? {};
            return (
              <div key={indicator} className="screener-filter-row">
                <label className="screener-filter-label">
                  {INDICATOR_LABELS[indicator]}
                </label>
                <div className="screener-filter-inputs">
                  <input
                    type="number"
                    step="any"
                    className="screener-filter-input"
                    placeholder={t("screener.min")}
                    value={bound.min ?? ""}
                    onChange={(event) =>
                      handleBoundChange(indicator, "min", event.target.value)
                    }
                  />
                  <input
                    type="number"
                    step="any"
                    className="screener-filter-input"
                    placeholder={t("screener.max")}
                    value={bound.max ?? ""}
                    onChange={(event) =>
                      handleBoundChange(indicator, "max", event.target.value)
                    }
                  />
                </div>
              </div>
            );
          })}
          <div className="screener-filter-actions">
            <button
              type="button"
              className="screener-filter-button"
              onClick={applyFilters}
              disabled={isFetching}
            >
              {t("screener.apply_filters")}
            </button>
            <button
              type="button"
              className="screener-filter-button"
              onClick={clearFilters}
            >
              {t("screener.clear_filters")}
            </button>
          </div>
        </aside>

        <section className="screener-results">
          <div className="screener-results-header">
            {isLoading
              ? t("screener.loading")
              : t("screener.results_count", { count: totalCount })}
          </div>

          <div className="screener-table-wrapper">
            <table className="screener-table">
              <thead>
                <tr>
                  <th onClick={() => toggleSort("ticker")}>
                    {t("screener.col_ticker")}
                  </th>
                  <th>{t("screener.col_name")}</th>
                  <th>{t("screener.col_sector")}</th>
                  {SCREENER_INDICATORS.map((indicator) => (
                    <th
                      key={indicator}
                      className="screener-value"
                      onClick={() => toggleSort(indicator)}
                    >
                      {INDICATOR_LABELS[indicator]}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 && !isLoading && (
                  <tr>
                    <td colSpan={3 + SCREENER_INDICATORS.length} className="screener-empty">
                      {t("screener.no_results")}
                    </td>
                  </tr>
                )}
                {rows.map((row) => (
                  <tr
                    key={row.ticker}
                    className="screener-table-row"
                    onClick={() => {
                      window.location.href = `/${locale}/${row.ticker}`;
                    }}
                  >
                    <td>
                      <Link
                        href={`/${locale}/${row.ticker}`}
                        className="screener-ticker"
                        onClick={(event) => event.stopPropagation()}
                      >
                        <img
                          src={logoUrl(row.ticker)}
                          alt=""
                          className="screener-ticker-logo"
                          onError={(event) => {
                            (event.target as HTMLImageElement).style.display = "none";
                          }}
                        />
                        {row.ticker}
                      </Link>
                    </td>
                    <td className="screener-name">{row.name || "—"}</td>
                    <td className="screener-sector">{row.sector || "—"}</td>
                    {SCREENER_INDICATORS.map((indicator) => (
                      <td key={indicator} className="screener-value">
                        {formatIndicatorValue(indicator, row[indicator], row.ticker)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {hasMore && (
            <>
              <div ref={sentinelRef} aria-hidden className="screener-scroll-sentinel" />
              <button
                type="button"
                className="screener-load-more"
                onClick={loadMore}
                disabled={isFetching}
              >
                {t("screener.load_more")}
              </button>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
