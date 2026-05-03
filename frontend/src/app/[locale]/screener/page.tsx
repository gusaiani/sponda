"use client";

import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import {
  useScreener,
  SCREENER_INDICATORS,
  ScreenerFilters,
  ScreenerIndicator,
} from "../../../hooks/useScreener";
import { DualRangeSlider } from "../../../components/DualRangeSlider";
import {
  CURRENT_RATIO_SCALE,
  LEVERAGE_SCALE,
  formatCurrentRatioValue,
  formatLeverageValue,
  type SliderScale,
} from "../../../utils/sliderScale";
import {
  ScreenerFilterPresets,
  SaveFilterPresetModal,
} from "../../../components/ScreenerFilterPresets";
import { useSavedScreenerFilters } from "../../../hooks/useSavedScreenerFilters";
import { useSavedLists } from "../../../hooks/useSavedLists";
import { useAuth } from "../../../hooks/useAuth";
import { AuthModal } from "../../../components/AuthModal";
import { useTranslation } from "../../../i18n";
import { formatLargeNumber, logoUrl, formatNumber } from "../../../utils/format";
import "../../../styles/compare.css";
import "../../../styles/screener.css";

const PAGE_SIZE = 20;

/** Screener indicators the user can set min/max bounds on. Market cap is
 * intentionally absent: users rank by it (default sort) and read it from
 * the table, but shouldn't screen by it as a numeric bound. 5y variants
 * of PE/PFCF and debt-ratio filters aren't in the backend yet — add them
 * here once the fields exist. */
type FilterIndicator = Exclude<ScreenerIndicator, "market_cap">;

/** Display order for the filter UI (inline strip + popover), ordered so
 * balance-sheet screens land first — this is the shortlist the user
 * tends to start a screening session with. */
const FILTER_ORDER: readonly FilterIndicator[] = [
  "debt_to_equity",
  "liabilities_to_equity",
  "current_ratio",
  "debt_to_avg_earnings",
  "debt_to_avg_fcf",
  "pe10",
  "pfcf10",
  "debt_ex_lease_to_equity",
  "peg",
  "pfcf_peg",
] as const;

/** Indicators surfaced as inline sliders in the header bar on wide
 * viewports. Picks the first slots of FILTER_ORDER; anything that
 * doesn't fit wraps into the popover via the overflow-detection hook. */
const INLINE_INDICATORS: readonly FilterIndicator[] = FILTER_ORDER.slice(0, 5);

/** The complement of INLINE_INDICATORS — shown inside the "mais filtros"
 * popover only, so users never see duplicate inputs for the same metric. */
const EXTRA_INDICATORS: readonly FilterIndicator[] = FILTER_ORDER.slice(5);

/** Human-readable labels for each indicator, shown in the filter panel
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
  debt_to_avg_earnings: "Debt / Avg Earnings (10y)",
  debt_to_avg_fcf: "Debt / Avg FCF (10y)",
  market_cap: "Market Cap",
};

/** Slider track bounds for each indicator. All start at 0 — the value
 * investor screener isn't meant to surface companies with negative
 * multiples or negative leverage. Max values are picked to cover the
 * realistic B3 range with a bit of headroom.
 *
 * Leverage ratios opt into a non-linear scale so the 0..1 band — where
 * most companies sit — gets generous resolution while distressed-balance
 * outliers (D/E up to ~100) still fit on the same track. */
interface IndicatorBounds {
  trackMin: number;
  trackMax: number;
  step: number;
  scale?: SliderScale;
  format?: (value: number, locale: string) => string;
}

const INDICATOR_BOUNDS: Record<FilterIndicator, IndicatorBounds> = {
  pe10: { trackMin: 0, trackMax: 50, step: 1 },
  pfcf10: { trackMin: 0, trackMax: 50, step: 1 },
  peg: { trackMin: 0, trackMax: 5, step: 0.1 },
  pfcf_peg: { trackMin: 0, trackMax: 5, step: 0.1 },
  debt_to_equity: {
    trackMin: 0,
    trackMax: 100,
    step: 0.05,
    scale: LEVERAGE_SCALE,
    format: formatLeverageValue,
  },
  debt_ex_lease_to_equity: {
    trackMin: 0,
    trackMax: 100,
    step: 0.05,
    scale: LEVERAGE_SCALE,
    format: formatLeverageValue,
  },
  liabilities_to_equity: {
    trackMin: 0,
    trackMax: 100,
    step: 0.05,
    scale: LEVERAGE_SCALE,
    format: formatLeverageValue,
  },
  current_ratio: {
    trackMin: 0,
    trackMax: 20,
    step: 0.05,
    scale: CURRENT_RATIO_SCALE,
    format: formatCurrentRatioValue,
  },
  debt_to_avg_earnings: { trackMin: 0, trackMax: 20, step: 0.5 },
  debt_to_avg_fcf: { trackMin: 0, trackMax: 20, step: 0.5 },
};

function SpondaCircleLogo() {
  return (
    <svg
      className="screener-header-logo-svg"
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 32 32"
      aria-hidden="true"
    >
      <circle cx="16" cy="16" r="16" fill="#1b347e" />
      <line x1="16" y1="2" x2="16" y2="7" stroke="#fff" strokeWidth="1.5" strokeLinecap="round" />
      <line x1="16" y1="25" x2="16" y2="30" stroke="#fff" strokeWidth="1.5" strokeLinecap="round" />
      <text
        x="16"
        y="21.5"
        fontFamily="Satoshi,system-ui,sans-serif"
        fontSize="18"
        fontWeight="500"
        fill="#fff"
        textAnchor="middle"
      >
        S
      </text>
    </svg>
  );
}

function ChevronDownIcon({ flipped }: { flipped: boolean }) {
  return (
    <svg
      width="12"
      height="12"
      viewBox="0 0 12 12"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      style={{ transform: flipped ? "rotate(180deg)" : undefined, transition: "transform 0.15s" }}
    >
      <polyline points="3 4.5 6 7.5 9 4.5" />
    </svg>
  );
}

/** Display the 'market_cap' column as a formatted currency; other
 * indicator columns are plain decimals. */
function formatIndicatorValue(
  indicator: ScreenerIndicator,
  rawValue: string | number | null,
  ticker: string,
  locale: string,
): string | null {
  if (rawValue === null || rawValue === undefined || rawValue === "") return null;
  const value = typeof rawValue === "string" ? Number(rawValue) : rawValue;
  if (Number.isNaN(value)) return null;
  if (indicator === "market_cap") {
    return formatLargeNumber(value, ticker, locale);
  }
  return formatNumber(value, 2, locale);
}

function emptyBounds(): ScreenerFilters["bounds"] {
  return {};
}

/** Derive the sortable key's direction from the `sort` filter string
 * (e.g. "-market_cap" → descending on market_cap). */
function parseSort(sort: string): { field: string; dir: "asc" | "desc" } {
  if (sort.startsWith("-")) return { field: sort.slice(1), dir: "desc" };
  return { field: sort, dir: "asc" };
}

export default function ScreenerPage() {
  const { t } = useTranslation();
  const params = useParams<{ locale: string }>();
  const locale = params?.locale || "pt";

  const [draftBounds, setDraftBounds] = useState<ScreenerFilters["bounds"]>(emptyBounds);
  const [appliedFilters, setAppliedFilters] = useState<ScreenerFilters>({
    bounds: {},
    sort: "-market_cap",
    limit: PAGE_SIZE,
    offset: 0,
  });
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [showSavePresetModal, setShowSavePresetModal] = useState(false);
  const [showSaveListModal, setShowSaveListModal] = useState(false);
  const [saveListName, setSaveListName] = useState("");
  const [saveListError, setSaveListError] = useState<string | null>(null);
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [pendingAuthAction, setPendingAuthAction] = useState<
    "save-list" | "save-preset" | null
  >(null);
  const queryClient = useQueryClient();
  const filtersWrapperRef = useRef<HTMLDivElement | null>(null);
  const inlineStripRef = useRef<HTMLDivElement | null>(null);

  const { isAuthenticated } = useAuth();
  const { saveFilter } = useSavedScreenerFilters();
  const { saveList } = useSavedLists();

  /** Tail of INLINE_INDICATORS that wrapped to a second line inside the
   * strip (and so are hidden by the strip's max-height + overflow:hidden).
   * We surface these in the popover so the user can still interact. */
  const [evictedFromInline, setEvictedFromInline] = useState<
    FilterIndicator[]
  >([]);

  /** Detect which fieldsets the browser wrapped to a second row inside
   * the strip. The strip is flex-wrap:wrap + max-height (one line) so
   * items past the first row are hidden — we read offsetTop to find
   * them rather than measuring widths ourselves, which is both simpler
   * and more reliable than caching widths and doing our own fit math. */
  const recomputeWrap = useCallback(() => {
    const node = inlineStripRef.current;
    if (!node) return;
    const items = node.querySelectorAll<HTMLElement>("[data-inline-indicator]");
    if (items.length === 0) return;
    const firstLineTop = items[0].offsetTop;
    const evicted: FilterIndicator[] = [];
    items.forEach((item) => {
      if (item.offsetTop > firstLineTop) {
        evicted.push(item.dataset.inlineIndicator as FilterIndicator);
      }
    });
    setEvictedFromInline((previous) => {
      if (
        previous.length === evicted.length &&
        previous.every((value, index) => value === evicted[index])
      ) {
        return previous;
      }
      return evicted;
    });
  }, []);

  useLayoutEffect(() => {
    recomputeWrap();
  }, [recomputeWrap]);

  useEffect(() => {
    const strip = inlineStripRef.current;
    if (!strip) return;
    const observer = new ResizeObserver(recomputeWrap);
    observer.observe(strip);
    window.addEventListener("resize", recomputeWrap);
    return () => {
      observer.disconnect();
      window.removeEventListener("resize", recomputeWrap);
    };
  }, [recomputeWrap]);

  /** Popover renders the evicted (tail) inline items first, then the
   * always-hidden extras. Dedupe is defensive in case the two sets ever
   * overlap (they don't today). */
  const popoverIndicators = useMemo<FilterIndicator[]>(() => {
    const seen = new Set<FilterIndicator>();
    const ordered: FilterIndicator[] = [];
    for (const indicator of [...evictedFromInline, ...EXTRA_INDICATORS]) {
      if (seen.has(indicator)) continue;
      seen.add(indicator);
      ordered.push(indicator);
    }
    return ordered;
  }, [evictedFromInline]);

  const { data, isLoading, isFetching } = useScreener(appliedFilters);
  const rows = data?.results ?? [];
  const totalCount = data?.count ?? 0;
  const hasMore = rows.length < totalCount;

  /** Only count extras (non-inline) because the badge sits on the
   * "mais filtros" toggle — inline inputs are already visible. */
  const extraFilterCount = useMemo(() => {
    let active = 0;
    for (const indicator of EXTRA_INDICATORS) {
      const bound = appliedFilters.bounds[indicator];
      if (!bound) continue;
      if ((bound.min && bound.min.trim()) || (bound.max && bound.max.trim())) {
        active += 1;
      }
    }
    return active;
  }, [appliedFilters.bounds]);

  const { field: sortField, dir: sortDir } = parseSort(appliedFilters.sort);

  // Close the filter popover on outside click or Escape key.
  useEffect(() => {
    if (!filtersOpen) return;
    function handlePointer(event: MouseEvent) {
      if (!filtersWrapperRef.current) return;
      if (filtersWrapperRef.current.contains(event.target as Node)) return;
      setFiltersOpen(false);
    }
    function handleKey(event: KeyboardEvent) {
      if (event.key === "Escape") setFiltersOpen(false);
    }
    document.addEventListener("mousedown", handlePointer);
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("mousedown", handlePointer);
      document.removeEventListener("keydown", handleKey);
    };
  }, [filtersOpen]);

  function handleSliderChange(
    indicator: FilterIndicator,
    next: { min: string | null; max: string | null },
  ) {
    setDraftBounds((previous) => {
      const updated = { ...previous };
      if (next.min === null && next.max === null) {
        delete updated[indicator];
      } else {
        updated[indicator] = {
          ...(next.min !== null ? { min: next.min } : {}),
          ...(next.max !== null ? { max: next.max } : {}),
        };
      }
      return updated;
    });
  }

  function applyFilters() {
    setAppliedFilters((previous) => ({
      ...previous,
      bounds: draftBounds,
      limit: PAGE_SIZE,
      offset: 0,
    }));
    setFiltersOpen(false);
  }

  function clearFilters() {
    setDraftBounds(emptyBounds());
    setAppliedFilters((previous) => ({
      ...previous,
      bounds: {},
      limit: PAGE_SIZE,
      offset: 0,
    }));
  }

  function applyPreset(preset: { bounds: ScreenerFilters["bounds"]; sort: string }) {
    setDraftBounds(preset.bounds);
    setAppliedFilters((previous) => ({
      ...previous,
      bounds: preset.bounds,
      sort: preset.sort,
      limit: PAGE_SIZE,
      offset: 0,
    }));
    setFiltersOpen(false);
  }

  function handleSavePreset(name: string) {
    saveFilter.mutate(
      { name, bounds: appliedFilters.bounds, sort: appliedFilters.sort },
      { onSuccess: () => setShowSavePresetModal(false) },
    );
  }

  function handleRequestSavePreset() {
    if (!isAuthenticated) {
      setPendingAuthAction("save-preset");
      setShowAuthModal(true);
      return;
    }
    setShowSavePresetModal(true);
  }

  function handleRequestSaveList() {
    if (rows.length === 0) return;
    if (!isAuthenticated) {
      setPendingAuthAction("save-list");
      setShowAuthModal(true);
      return;
    }
    setSaveListError(null);
    setShowSaveListModal(true);
  }

  function handleAuthSuccess() {
    const nextAction = pendingAuthAction;
    setShowAuthModal(false);
    setPendingAuthAction(null);
    queryClient.invalidateQueries({ queryKey: ["auth-user"] }).then(() => {
      if (nextAction === "save-list") {
        setSaveListError(null);
        setShowSaveListModal(true);
      } else if (nextAction === "save-preset") {
        setShowSavePresetModal(true);
      }
    });
  }

  function handleAuthClose() {
    setShowAuthModal(false);
    setPendingAuthAction(null);
  }

  function handleSaveList(event: React.FormEvent) {
    event.preventDefault();
    const trimmed = saveListName.trim();
    if (!trimmed) return;
    const tickers = rows.map((row) => row.ticker);
    setSaveListError(null);
    saveList.mutate(
      { name: trimmed, tickers, years: 10 },
      {
        onSuccess: (saved) => {
          setShowSaveListModal(false);
          setSaveListName("");
          setSaveListError(null);
          const firstTicker = tickers[0];
          if (firstTicker) {
            window.location.href = `/${locale}/${firstTicker}/comparar?listId=${saved.id}`;
          }
        },
        onError: (error: unknown) => {
          const message =
            error instanceof Error ? error.message : "Failed to save list";
          setSaveListError(message);
        },
      },
    );
  }

  function toggleSort(field: string) {
    setAppliedFilters((previous) => {
      const currentlyDescendingOnField = previous.sort === `-${field}`;
      const nextSort = currentlyDescendingOnField ? field : `-${field}`;
      return { ...previous, sort: nextSort, limit: PAGE_SIZE, offset: 0 };
    });
  }

  const loadMore = useCallback(() => {
    setAppliedFilters((previous) => ({
      ...previous,
      limit: previous.limit + PAGE_SIZE,
    }));
  }, []);

  function sortIndicator(field: string) {
    if (sortField !== field) {
      return <span className="compare-sort-arrow compare-sort-inactive">↕</span>;
    }
    return <span className="compare-sort-arrow">{sortDir === "asc" ? "↑" : "↓"}</span>;
  }

  return (
    <div className="screener-page">
      <div className="screener-header" ref={filtersWrapperRef}>
        <div className="screener-header-left">
          <span className="screener-header-logo">
            <SpondaCircleLogo />
          </span>
          <h1 className="screener-header-name">{t("screener.page_title")}</h1>
        </div>

        <div className="screener-header-inline-filters" ref={inlineStripRef}>
          {INLINE_INDICATORS.map((indicator) => {
            const bound = draftBounds[indicator] ?? {};
            const sliderBounds = INDICATOR_BOUNDS[indicator];
            return (
              <div
                key={indicator}
                className="screener-inline-filter"
                data-inline-indicator={indicator}
              >
                <label className="screener-inline-label">
                  {INDICATOR_LABELS[indicator]}
                </label>
                <DualRangeSlider
                  trackMin={sliderBounds.trackMin}
                  trackMax={sliderBounds.trackMax}
                  step={sliderBounds.step}
                  scale={sliderBounds.scale}
                  minValue={bound.min ?? null}
                  maxValue={bound.max ?? null}
                  format={sliderBounds.format
                    ? (value) => sliderBounds.format!(value, locale)
                    : undefined}
                  locale={locale}
                  onChange={(value) => handleSliderChange(indicator, value)}
                />
              </div>
            );
          })}
        </div>

        <div className="screener-header-filters">
          <button
            type="button"
            className="screener-filter-toggle"
            onClick={() => setFiltersOpen((open) => !open)}
            aria-expanded={filtersOpen}
            aria-controls="screener-filter-popover"
          >
            <span>{t("screener.more_filters")}</span>
            {extraFilterCount > 0 && (
              <span className="screener-filter-count">{extraFilterCount}</span>
            )}
            <ChevronDownIcon flipped={filtersOpen} />
          </button>
        </div>

        <button
          type="button"
          className="screener-filter-apply"
          onClick={applyFilters}
          disabled={isFetching}
        >
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <span>{t("screener.apply_filters")}</span>
        </button>

        {filtersOpen && (
          <div
            id="screener-filter-popover"
            className="screener-filter-popover"
            role="dialog"
            aria-label={t("screener.more_filters")}
          >
            <div className="screener-popover-filters">
              {popoverIndicators.map((indicator) => {
                const bound = draftBounds[indicator] ?? {};
                const sliderBounds = INDICATOR_BOUNDS[indicator];
                return (
                  <div key={indicator} className="screener-inline-filter">
                    <label className="screener-inline-label">
                      {INDICATOR_LABELS[indicator]}
                    </label>
                    <DualRangeSlider
                      trackMin={sliderBounds.trackMin}
                      trackMax={sliderBounds.trackMax}
                      step={sliderBounds.step}
                      scale={sliderBounds.scale}
                      minValue={bound.min ?? null}
                      maxValue={bound.max ?? null}
                      format={sliderBounds.format
                        ? (value) => sliderBounds.format!(value, locale)
                        : undefined}
                      locale={locale}
                      onChange={(value) => handleSliderChange(indicator, value)}
                    />
                  </div>
                );
              })}
            </div>
            <div className="screener-filter-actions">
              <button
                type="button"
                className="screener-filter-button"
                onClick={clearFilters}
              >
                {t("screener.clear_filters")}
              </button>
            </div>
          </div>
        )}
      </div>

      <ScreenerFilterPresets
        currentBounds={appliedFilters.bounds}
        currentSort={appliedFilters.sort}
        onApplyPreset={applyPreset}
        onRequestSave={handleRequestSavePreset}
      />

      <div className="screener-table-section">
        <div className="compare-scroll-wrapper">
          <table className="compare-table screener-compare-table">
            <thead>
              <tr>
                <th className="compare-sticky-col">{t("compare.company")}</th>
                {SCREENER_INDICATORS.map((indicator) => (
                  <th
                    key={indicator}
                    className="compare-sortable-th"
                    onClick={() => toggleSort(indicator)}
                  >
                    {INDICATOR_LABELS[indicator]} {sortIndicator(indicator)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 && !isLoading && (
                <tr>
                  <td
                    colSpan={SCREENER_INDICATORS.length + 1}
                    className="screener-empty"
                  >
                    {t("screener.no_results")}
                  </td>
                </tr>
              )}
              {rows.map((row) => (
                <tr key={row.ticker}>
                  <td className="compare-sticky-col">
                    <div className="compare-company-cell">
                      <Link
                        href={`/${locale}/${row.ticker}`}
                        className="compare-company-link"
                      >
                        <img
                          className="compare-company-logo"
                          src={logoUrl(row.ticker)}
                          alt=""
                          onError={(event) => {
                            (event.target as HTMLImageElement).style.display = "none";
                          }}
                        />
                        <span className="compare-company-name" title={row.name}>
                          {row.name || row.ticker}
                        </span>
                        <span className="compare-company-ticker">{row.ticker}</span>
                      </Link>
                    </div>
                  </td>
                  {SCREENER_INDICATORS.map((indicator) => {
                    const formatted = formatIndicatorValue(
                      indicator,
                      row[indicator],
                      row.ticker,
                      locale,
                    );
                    return (
                      <td key={indicator}>
                        {formatted !== null ? (
                          formatted
                        ) : (
                          <span className="compare-null">—</span>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
              {hasMore && (
                <tr className="screener-show-more-row">
                  <td colSpan={SCREENER_INDICATORS.length + 1}>
                    <button
                      type="button"
                      className="screener-show-more-button"
                      onClick={loadMore}
                      disabled={isFetching}
                    >
                      {t("screener.load_more")}
                    </button>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {rows.length > 0 && (
          <div className="screener-floating-actions">
            <button
              type="button"
              className="compare-save-floating"
              onClick={handleRequestSaveList}
            >
              {t("screener.save_as_list")}
            </button>
          </div>
        )}
      </div>

      {showSavePresetModal && (
        <SaveFilterPresetModal
          onSave={handleSavePreset}
          onCancel={() => setShowSavePresetModal(false)}
        />
      )}

      {showSaveListModal && (
        <div className="compare-save-overlay" onClick={() => { setShowSaveListModal(false); setSaveListError(null); }}>
          <div className="compare-save-modal" onClick={(event) => event.stopPropagation()}>
            <h3 className="compare-save-modal-title">{t("screener.save_as_list")}</h3>
            <p className="compare-save-modal-detail">
              {rows.length} {t("common.companies")}
            </p>
            <form onSubmit={handleSaveList}>
              <input
                type="text"
                className="auth-input"
                placeholder={t("screener.list_name_placeholder")}
                value={saveListName}
                onChange={(event) => setSaveListName(event.target.value)}
                autoFocus
              />
              {saveListError && (
                <p className="auth-error">{saveListError}</p>
              )}
              <div className="compare-save-modal-actions">
                <button type="submit" className="auth-button" disabled={!saveListName.trim() || saveList.isPending}>
                  {t("common.save")}
                </button>
                <button
                  type="button"
                  className="auth-button-secondary"
                  onClick={() => { setShowSaveListModal(false); setSaveListError(null); }}
                >
                  {t("common.cancel")}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showAuthModal && (
        <AuthModal
          onSuccess={handleAuthSuccess}
          onClose={handleAuthClose}
        />
      )}
    </div>
  );
}
