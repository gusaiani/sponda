"use client";

import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";
import { useTranslation } from "../i18n";
import { formatNumber, currencySymbolForCode } from "../utils/format";
import type { DataPoint } from "./MiniChart";
import { YearsSlider } from "./YearsSlider";
import { CompanySearchInput } from "./CompanySearchInput";
import { indicatorKind, isRebasable } from "../utils/indicatorKinds";
import {
  buildAlignedDataset,
  convertSeries,
  hasMixedCurrencies,
  timestampToLabel,
  type NamedSeries,
} from "../utils/normalizeSeries";
import { useComparisonSeries } from "../hooks/useComparisonSeries";
import { useFxSeriesMany } from "../hooks/useFxSeries";

const DEFAULT_CHART_COLOR = "#1e40af";
const MIN_POINTS_FOR_CHART = 2;
const MAX_X_AXIS_TICKS = 12;

/** Distinct per-company line colors. Index 0 is the primary company. */
const SERIES_COLORS = [
  "#1e40af",
  "#d97706",
  "#16a34a",
  "#8b5cf6",
  "#06b6d4",
  "#db2777",
];

function makeDefaultFormat(locale: string) {
  return (value: number): string => {
    if (Math.abs(value) >= 1e9) return `${formatNumber(value / 1e9, 1, locale)}B`;
    if (Math.abs(value) >= 1e6) return `${formatNumber(value / 1e6, 1, locale)}M`;
    if (Math.abs(value) >= 1e3) return `${formatNumber(value / 1e3, 1, locale)}K`;
    return formatNumber(value, 2, locale);
  };
}

function DetailedTooltipContent({ active, payload, formatValue }: {
  active?: boolean;
  payload?: { value: number; payload: DataPoint }[];
  formatValue: (value: number) => string;
}) {
  if (!active || !payload?.length) return null;
  const point = payload[0];
  return (
    <div className="detailed-chart-tooltip">
      <span className="detailed-chart-tooltip-label">{point.payload.label}</span>
      <span className="detailed-chart-tooltip-value">{formatValue(point.value)}</span>
    </div>
  );
}

interface DetailedChartProps {
  data: DataPoint[];
  color?: string;
  formatValue?: (value: number) => string;
}

/**
 * Full-detail line chart for the expanded view: y-axis with formatted ticks,
 * gridlines, and every meaningful x-axis label. Shares the same DataPoint
 * series the MiniChart renders, so the expanded view always matches the
 * thumbnail.
 */
export function DetailedChart({ data, color = DEFAULT_CHART_COLOR, formatValue }: DetailedChartProps) {
  const { locale } = useTranslation();
  const effectiveFormatValue = formatValue ?? makeDefaultFormat(locale);
  if (data.length < MIN_POINTS_FOR_CHART) return null;

  const indexed = data.map((point, index) => ({ ...point, idx: index }));

  // Year-boundary ticks when the series carries them; otherwise evenly spaced.
  const hasYearTicks = data[0]?.yearTick !== undefined;
  let xAxisTicks: number[] = [];
  if (hasYearTicks) {
    let lastTick = "";
    for (let index = 0; index < data.length; index++) {
      const tick = data[index].yearTick ?? "";
      if (tick !== lastTick) {
        xAxisTicks.push(index);
        lastTick = tick;
      }
    }
  } else {
    xAxisTicks = data.map((_, index) => index);
  }
  if (xAxisTicks.length > MAX_X_AXIS_TICKS) {
    const step = Math.ceil(xAxisTicks.length / MAX_X_AXIS_TICKS);
    xAxisTicks = xAxisTicks.filter((_, index) => index % step === 0);
  }

  return (
    <div className="detailed-chart">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={indexed} margin={{ top: 16, right: 24, left: 8, bottom: 8 }}>
          <CartesianGrid stroke="#e3e9f4" strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="idx"
            type="number"
            domain={[0, data.length - 1]}
            tickLine={false}
            axisLine={{ stroke: "#d0daea" }}
            tick={{ fontSize: 12, fill: "#5570a0" }}
            ticks={xAxisTicks}
            tickFormatter={(idx: number) => {
              const point = data[idx];
              if (!point) return "";
              if (hasYearTicks) return point.yearTick ?? "";
              return String(point.label);
            }}
          />
          <YAxis
            tickLine={false}
            axisLine={{ stroke: "#d0daea" }}
            tick={{ fontSize: 12, fill: "#5570a0" }}
            width={56}
            tickFormatter={(value: number) => effectiveFormatValue(value)}
          />
          <Tooltip
            content={<DetailedTooltipContent formatValue={effectiveFormatValue} />}
            cursor={{ stroke: "#d0daea", strokeWidth: 1 }}
          />
          <Line
            type="monotone"
            dataKey="value"
            stroke={color}
            strokeWidth={2}
            dot={{ r: 2.5, fill: color, stroke: "#fff", strokeWidth: 1 }}
            activeDot={{ r: 5, fill: color, stroke: "#fff", strokeWidth: 2 }}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

interface ExpandButtonProps {
  label: string;
  onClick: () => void;
}

/** Maximize button shown next to share/alert; opens the fullscreen chart. */
export function ExpandButton({ label, onClick }: ExpandButtonProps) {
  return (
    <button
      className="expand-btn"
      type="button"
      aria-label={label}
      title={label}
      onClick={(event) => {
        event.stopPropagation();
        onClick();
      }}
    >
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <polyline points="15 3 21 3 21 9" />
        <polyline points="9 21 3 21 3 15" />
        <line x1="21" y1="3" x2="14" y2="10" />
        <line x1="3" y1="21" x2="10" y2="14" />
      </svg>
    </button>
  );
}

/* ── Multi-company comparison chart ── */

type ScaleMode = "absolute" | "indexed" | "indexed-fx";

function ComparisonTooltip({ active, payload, label, names, formatValue, indexed, locale }: {
  active?: boolean;
  payload?: { value: number | null; dataKey: string; color: string }[];
  label?: number;
  names: Record<string, string>;
  formatValue: (value: number) => string;
  indexed: boolean;
  locale: string;
}) {
  if (!active || !payload?.length || label == null) return null;
  const rows = payload.filter((row) => row.value != null);
  if (!rows.length) return null;
  return (
    <div className="detailed-chart-tooltip">
      <span className="detailed-chart-tooltip-label">{timestampToLabel(Number(label))}</span>
      {rows.map((row) => (
        <span key={row.dataKey} className="detailed-chart-tooltip-row" style={{ color: row.color }}>
          <span className="detailed-chart-tooltip-name">{names[row.dataKey] ?? row.dataKey}</span>
          <span className="detailed-chart-tooltip-value">
            {indexed ? formatNumber(row.value as number, 1, locale) : formatValue(row.value as number)}
          </span>
        </span>
      ))}
    </div>
  );
}

interface ComparisonChartProps {
  series: NamedSeries[];
  rebase: boolean;
  logScale: boolean;
  formatValue: (value: number) => string;
}

/** Renders one line per company on a shared time axis. */
function ComparisonChart({ series, rebase, logScale, formatValue }: ComparisonChartProps) {
  const { locale } = useTranslation();
  const { rows, tickers } = useMemo(
    () => buildAlignedDataset(series, { rebase }),
    [series, rebase],
  );
  if (rows.length < MIN_POINTS_FOR_CHART) return null;

  const names: Record<string, string> = {};
  const colors: Record<string, string> = {};
  for (const entry of series) {
    names[entry.ticker] = entry.name;
    colors[entry.ticker] = entry.color;
  }

  // One tick per calendar-year boundary, thinned to a sane maximum.
  let yearTicks: number[] = [];
  let lastYear = "";
  for (const row of rows) {
    const year = String(new Date(row.t).getUTCFullYear());
    if (year !== lastYear) {
      yearTicks.push(row.t);
      lastYear = year;
    }
  }
  if (yearTicks.length > MAX_X_AXIS_TICKS) {
    const step = Math.ceil(yearTicks.length / MAX_X_AXIS_TICKS);
    yearTicks = yearTicks.filter((_, index) => index % step === 0);
  }

  return (
    <div className="detailed-chart">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={rows} margin={{ top: 16, right: 24, left: 8, bottom: 8 }}>
          <CartesianGrid stroke="#e3e9f4" strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="t"
            type="number"
            domain={[rows[0].t, rows[rows.length - 1].t]}
            tickLine={false}
            axisLine={{ stroke: "#d0daea" }}
            tick={{ fontSize: 12, fill: "#5570a0" }}
            ticks={yearTicks}
            tickFormatter={(t: number) => String(new Date(t).getUTCFullYear()).slice(2)}
          />
          <YAxis
            tickLine={false}
            axisLine={{ stroke: "#d0daea" }}
            tick={{ fontSize: 12, fill: "#5570a0" }}
            width={56}
            scale={logScale ? "log" : "auto"}
            domain={logScale ? ["auto", "auto"] : undefined}
            allowDataOverflow={logScale}
            tickFormatter={(value: number) => (rebase ? formatNumber(value, 0, locale) : formatValue(value))}
          />
          <Tooltip
            content={(
              <ComparisonTooltip
                names={names}
                formatValue={formatValue}
                indexed={rebase}
                locale={locale}
              />
            )}
            cursor={{ stroke: "#d0daea", strokeWidth: 1 }}
          />
          {tickers.map((ticker) => (
            <Line
              key={ticker}
              type="monotone"
              dataKey={ticker}
              name={names[ticker]}
              stroke={colors[ticker]}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, fill: colors[ticker], stroke: "#fff", strokeWidth: 1.5 }}
              connectNulls
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

interface PrimaryCompany {
  ticker: string;
  name: string;
  currency: string;
  points: DataPoint[];
}

interface IndicatorChartModalProps {
  indicatorLabel: string;
  metricId: string;
  primary: PrimaryCompany;
  formatValue?: (value: number) => string;
  years: number;
  maxYears: number;
  onYearsChange: (years: number) => void;
  onClose: () => void;
}

/**
 * Whole-window overlay for one indicator. Beyond the single-company chart it
 * carries the term slider, lets the user overlay other companies, and — for
 * currency-denominated indicators — rebases (and optionally FX-converts) the
 * series so they are comparable. Closes on Escape, backdrop click, or the
 * close button; locks body scroll while open.
 */
export function IndicatorChartModal({
  indicatorLabel,
  metricId,
  primary,
  formatValue,
  years,
  maxYears,
  onYearsChange,
  onClose,
}: IndicatorChartModalProps) {
  const { t, locale } = useTranslation();
  const [compareTickers, setCompareTickers] = useState<string[]>([]);
  const [scaleMode, setScaleMode] = useState<ScaleMode>("indexed");
  const [logScale, setLogScale] = useState(false);

  const effectiveFormatValue = formatValue ?? ((value: number) => formatNumber(value, 2, locale));
  const kind = indicatorKind(metricId);
  const rebasable = isRebasable(kind);

  useEffect(() => {
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", handleKey);
      document.body.style.overflow = "";
    };
  }, [onClose]);

  const comparison = useComparisonSeries(compareTickers, years);

  // Raw (pre-conversion) series for the active indicator, one per company.
  const rawSeries: NamedSeries[] = useMemo(() => {
    const list: NamedSeries[] = [
      {
        ticker: primary.ticker,
        name: primary.name,
        color: SERIES_COLORS[0],
        currency: primary.currency,
        points: primary.points,
      },
    ];
    comparison.forEach((company, index) => {
      const points = company.chartData?.[metricId];
      if (points && points.length >= MIN_POINTS_FOR_CHART) {
        list.push({
          ticker: company.ticker,
          name: company.name,
          color: SERIES_COLORS[(index + 1) % SERIES_COLORS.length],
          currency: company.currency,
          points,
        });
      }
    });
    return list;
  }, [primary, comparison, metricId]);

  const multi = rawSeries.length >= 2;
  const mixed = hasMixedCurrencies(rawSeries);
  const showScaleToggle = rebasable && multi;
  const showLogToggle = kind === "ratio" && multi;

  // Resolve the effective scale: only-rebasable metrics may rebase; absolute is
  // forbidden across currencies (a shared currency axis would be misleading).
  let resolvedScale: ScaleMode = showScaleToggle ? scaleMode : "absolute";
  if (resolvedScale === "absolute" && mixed && rebasable) resolvedScale = "indexed";

  // For common-currency mode, fetch FX from every foreign currency → primary's.
  const foreignCurrencies = useMemo(() => {
    const set = new Set<string>();
    for (const entry of rawSeries) {
      if (entry.currency !== primary.currency) set.add(entry.currency);
    }
    return [...set];
  }, [rawSeries, primary.currency]);
  const fxByCurrency = useFxSeriesMany(
    foreignCurrencies,
    primary.currency,
    resolvedScale === "indexed-fx",
  );

  const processedSeries: NamedSeries[] = useMemo(() => {
    if (resolvedScale !== "indexed-fx") return rawSeries;
    return rawSeries.map((entry) =>
      entry.currency === primary.currency
        ? entry
        : { ...entry, points: convertSeries(entry.points, fxByCurrency[entry.currency] ?? []) },
    );
  }, [rawSeries, resolvedScale, fxByCurrency, primary.currency]);

  const fxPending =
    resolvedScale === "indexed-fx" &&
    foreignCurrencies.some((currency) => (fxByCurrency[currency] ?? []).length === 0);

  const commonCurrencyLabel = currencySymbolForCode(primary.currency);

  return createPortal(
    <div className="chart-fullscreen-overlay" onClick={onClose}>
      <div className="chart-fullscreen-content" onClick={(event) => event.stopPropagation()}>
        <div className="chart-fullscreen-header">
          <div className="chart-fullscreen-titles">
            <h2 className="chart-fullscreen-title">{indicatorLabel} — {primary.name}</h2>
          </div>
          <button
            className="chart-fullscreen-close"
            type="button"
            aria-label={t("common.close")}
            onClick={onClose}
          >
            ×
          </button>
        </div>

        <div className="chart-fullscreen-controls">
          {maxYears > 1 && (
            <YearsSlider years={years} maxYears={maxYears} onYearsChange={onYearsChange} />
          )}
          <div className="chart-fullscreen-add">
            <CompanySearchInput
              onAdd={(ticker) =>
                setCompareTickers((current) =>
                  current.includes(ticker) || ticker === primary.ticker
                    ? current
                    : [...current, ticker],
                )
              }
              excludeTickers={[primary.ticker, ...compareTickers]}
            />
          </div>
          {showScaleToggle && (
            <div className="chart-scale-toggle" role="group" aria-label={t("chart.scale_group")}>
              <button
                type="button"
                className={`chart-scale-btn${resolvedScale === "absolute" ? " chart-scale-btn--active" : ""}`}
                disabled={mixed}
                onClick={() => setScaleMode("absolute")}
              >
                {t("chart.scale_absolute")}
              </button>
              <button
                type="button"
                className={`chart-scale-btn${resolvedScale === "indexed" ? " chart-scale-btn--active" : ""}`}
                onClick={() => setScaleMode("indexed")}
              >
                {t("chart.scale_indexed")}
              </button>
              <button
                type="button"
                className={`chart-scale-btn${resolvedScale === "indexed-fx" ? " chart-scale-btn--active" : ""}`}
                onClick={() => setScaleMode("indexed-fx")}
              >
                {t("chart.scale_indexed_fx")} · {commonCurrencyLabel}
              </button>
            </div>
          )}
          {showLogToggle && (
            <label className="chart-log-toggle">
              <input
                type="checkbox"
                checked={logScale}
                onChange={(event) => setLogScale(event.target.checked)}
              />
              {t("chart.log_scale")}
            </label>
          )}
        </div>

        <div className="chart-fullscreen-legend">
          {rawSeries.map((entry) => (
            <span key={entry.ticker} className="chart-legend-item">
              <span className="chart-legend-swatch" style={{ background: entry.color }} />
              <span className="chart-legend-name">{entry.name}</span>
              {entry.ticker !== primary.ticker && (
                <button
                  type="button"
                  className="chart-legend-remove"
                  aria-label={t("common.remove")}
                  onClick={() =>
                    setCompareTickers((current) => current.filter((ticker) => ticker !== entry.ticker))
                  }
                >
                  ×
                </button>
              )}
            </span>
          ))}
        </div>

        {fxPending && <div className="chart-fx-note">{t("chart.fx_warning")}</div>}

        <div className="chart-fullscreen-body">
          <ComparisonChart
            series={processedSeries}
            rebase={resolvedScale !== "absolute"}
            logScale={logScale}
            formatValue={effectiveFormatValue}
          />
        </div>
      </div>
    </div>,
    document.body,
  );
}
