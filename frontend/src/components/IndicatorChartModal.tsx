"use client";

import { useEffect } from "react";
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
import { formatNumber } from "../utils/format";
import type { DataPoint } from "./MiniChart";

const DEFAULT_CHART_COLOR = "#1e40af";
const MIN_POINTS_FOR_CHART = 2;
const MAX_X_AXIS_TICKS = 12;

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

interface IndicatorChartModalProps {
  title: string;
  currentValue?: string;
  data: DataPoint[];
  color?: string;
  formatValue?: (value: number) => string;
  onClose: () => void;
}

/**
 * Whole-window overlay that shows a single indicator's chart in full detail.
 * Closes on Escape, backdrop click, or the close button; locks body scroll
 * while open.
 */
export function IndicatorChartModal({
  title,
  currentValue,
  data,
  color,
  formatValue,
  onClose,
}: IndicatorChartModalProps) {
  const { t } = useTranslation();

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

  return createPortal(
    <div className="chart-fullscreen-overlay" onClick={onClose}>
      <div className="chart-fullscreen-content" onClick={(event) => event.stopPropagation()}>
        <div className="chart-fullscreen-header">
          <div className="chart-fullscreen-titles">
            <h2 className="chart-fullscreen-title">{title}</h2>
            {currentValue && <span className="chart-fullscreen-value">{currentValue}</span>}
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
        <div className="chart-fullscreen-body">
          <DetailedChart data={data} color={color} formatValue={formatValue} />
        </div>
      </div>
    </div>,
    document.body,
  );
}
