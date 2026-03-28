import { useCallback, useRef, useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceDot,
  ResponsiveContainer,
} from "recharts";
import type { MultiplesHistoryResult } from "../hooks/useMultiplesHistory";
import "../styles/chart.css";

type MultipleType = "pl" | "pfcl";

const LABELS: Record<MultipleType, string> = {
  pl: "P/L10",
  pfcl: "P/FCL10",
};

const PRICE_COLOR = "#1e40af"; // --color-accent
const MULTIPLE_COLOR = "#d97706"; // amber-600

/** Format number with Brazilian convention (comma as decimal separator). */
export function brFmt(n: number, decimals = 2): string {
  return n.toLocaleString("pt-BR", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

const MONTH_NAMES = [
  "jan", "fev", "mar", "abr", "mai", "jun",
  "jul", "ago", "set", "out", "nov", "dez",
];

/** Convert an ISO-style date string ("2024-01-31") to "jan/24". */
export function formatPriceDate(dateString: string): string {
  const [year, month] = dateString.split("-");
  const label = `${MONTH_NAMES[parseInt(month, 10) - 1]}/${year.slice(2)}`;
  return label;
}

/** Calculate a tick interval that shows roughly 8 ticks on the X axis. */
export function calculateTickInterval(dataLength: number): number {
  return Math.max(1, Math.floor(dataLength / 8));
}

interface PriceTooltipProps {
  active?: boolean;
  payload?: { value: number }[];
  label?: string;
}

function PriceTooltip({ active, payload, label }: PriceTooltipProps) {
  if (!active || !payload?.length) return null;
  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip-label">{label}</div>
      <div>R$ {brFmt(payload[0].value)}</div>
    </div>
  );
}

interface MultipleTooltipProps {
  active?: boolean;
  payload?: { value: number | null }[];
  label?: string;
  multipleLabel: string;
}

function MultipleTooltip({
  active,
  payload,
  label,
  multipleLabel,
}: MultipleTooltipProps) {
  if (!active || !payload?.length) return null;
  const val = payload[0].value;
  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip-label">{label}</div>
      <div>
        {multipleLabel}: {val != null ? brFmt(val) : "—"}
      </div>
    </div>
  );
}

interface Props {
  data: MultiplesHistoryResult;
}

export function MultiplesChart({ data }: Props) {
  const [activeMultiple, setActiveMultiple] = useState<MultipleType>("pl");
  const [showPriceInfo, setShowPriceInfo] = useState(false);
  const [hoveredYear, setHoveredYear] = useState<number | null>(null);
  const [hoveredX, setHoveredX] = useState<number | null>(null);
  const bottomPanelRef = useRef<HTMLDivElement>(null);

  const multiplesData = data.multiples[activeMultiple];

  // Extract year and X position from price chart hover
  const handlePriceMouseMove = useCallback(
    (state: { activeLabel?: string | number; chartX?: number }) => {
      if (!state.activeLabel) {
        setHoveredYear(null);
        setHoveredX(null);
        return;
      }
      const parts = String(state.activeLabel).split("/");
      if (parts.length === 2) {
        const shortYear = parseInt(parts[1], 10);
        const fullYear = (shortYear < 50 ? 2000 : 1900) + shortYear - 1;
        setHoveredYear(fullYear);
        setHoveredX(state.chartX ?? null);
      }
    },
    [],
  );

  const handlePriceMouseLeave = useCallback(() => {
    setHoveredYear(null);
    setHoveredX(null);
  }, []);

  if (!data.prices.length) {
    return (
      <div className="chart-container">
        <div className="chart-empty">Dados históricos indisponíveis</div>
      </div>
    );
  }

  // Format dates for display: "2015-01-31" → "jan/15"
  const priceData = data.prices.map((p) => ({
    date: formatPriceDate(p.date),
    adjustedClose: p.adjustedClose,
  }));

  // Show ~8 ticks on X axis regardless of data length
  const tickInterval = calculateTickInterval(priceData.length);

  // Find the hovered year's data in multiplesData; fall back to nearest year
  const hoveredMultiple = (() => {
    if (hoveredYear == null) return null;
    const exact = multiplesData.find((p) => p.year === hoveredYear);
    if (exact) return exact;
    // Find nearest year that has data
    let nearest = null;
    let minDist = Infinity;
    for (const p of multiplesData) {
      const dist = Math.abs(p.year - hoveredYear);
      if (dist < minDist) {
        minDist = dist;
        nearest = p;
      }
    }
    return nearest;
  })();

  return (
    <div className="chart-container">
      {/* Price panel */}
      <div className="chart-panel">
        <div className="chart-panel-title">
          Preço ajustado (R$)
          <button
            className="info-btn"
            aria-label="O que é preço ajustado?"
            onClick={() => setShowPriceInfo(!showPriceInfo)}
          >
            ?
          </button>
        </div>
        {showPriceInfo && (
          <p className="chart-info-text">
            Preço ajustado por dividendos e desdobramentos. Reflete o retorno
            total do acionista, como se todos os proventos tivessem sido
            reinvestidos na ação. Diferente do preço nominal, permite comparar
            períodos sem distorção por eventos corporativos.
          </p>
        )}
        <ResponsiveContainer width="100%" height={220}>
          <LineChart
            data={priceData}
            margin={{ top: 5, right: 10, left: 0, bottom: 5 }}
            onMouseMove={handlePriceMouseMove}
            onMouseLeave={handlePriceMouseLeave}
          >
            <CartesianGrid horizontal vertical={false} stroke="#f0f3f8" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 10, fill: "#94a3b8" }}
              interval={tickInterval}
              tickLine={false}
              axisLine={{ stroke: "#e2e8f0" }}
            />
            <YAxis
              tick={{ fontSize: 10, fill: "#94a3b8" }}
              tickLine={false}
              axisLine={false}
              width={50}
              tickFormatter={(v: number) => brFmt(v, 0)}
            />
            <Tooltip content={<PriceTooltip />} />
            <Line
              type="monotone"
              dataKey="adjustedClose"
              stroke={PRICE_COLOR}
              strokeWidth={1.5}
              dot={false}
              activeDot={{ r: 3, fill: PRICE_COLOR }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Multiple toggle */}
      <div className="multiple-toggle">
        {(["pl", "pfcl"] as MultipleType[]).map((key) => (
          <button
            key={key}
            className={`multiple-pill ${activeMultiple === key ? "multiple-pill-active" : ""}`}
            onClick={() => setActiveMultiple(key)}
          >
            {LABELS[key]}
          </button>
        ))}
      </div>

      {/* Multiples panel */}
      <div className="chart-panel" ref={bottomPanelRef} style={{ position: "relative" }}>
        <div className="chart-panel-title">
          {LABELS[activeMultiple]} histórico
        </div>
        <ResponsiveContainer width="100%" height={180}>
          <LineChart
            data={multiplesData}
            margin={{ top: 5, right: 10, left: 0, bottom: 5 }}
          >
            <CartesianGrid horizontal vertical={false} stroke="#f0f3f8" />
            <XAxis
              dataKey="year"
              tick={{ fontSize: 10, fill: "#94a3b8" }}
              tickLine={false}
              axisLine={{ stroke: "#e2e8f0" }}
            />
            <YAxis
              tick={{ fontSize: 10, fill: "#94a3b8" }}
              tickLine={false}
              axisLine={false}
              width={50}
              tickFormatter={(v: number) => brFmt(v, 1)}
            />
            <Tooltip
              content={
                <MultipleTooltip multipleLabel={LABELS[activeMultiple]} />
              }
            />
            <Line
              type="monotone"
              dataKey="value"
              stroke="transparent"
              strokeWidth={0}
              dot={{ r: 3, fill: MULTIPLE_COLOR, strokeWidth: 0 }}
              activeDot={{ r: 5, fill: MULTIPLE_COLOR, strokeWidth: 0 }}
              connectNulls
            />
            {/* Highlight synced year from price chart hover */}
            {hoveredMultiple && hoveredMultiple.value != null && (
              <ReferenceDot
                x={hoveredMultiple.year}
                y={hoveredMultiple.value}
                r={6}
                fill={MULTIPLE_COLOR}
                stroke="#ffffff"
                strokeWidth={2}
              />
            )}
          </LineChart>
        </ResponsiveContainer>
        {/* Floating synced tooltip — follows mouse X from price chart */}
        {hoveredYear != null && hoveredX != null && (
          <div
            className="chart-tooltip chart-synced-tooltip"
            style={{ left: hoveredX + 50 }}
          >
            <div className="chart-tooltip-label">{hoveredMultiple?.year ?? hoveredYear}</div>
            <div>
              {LABELS[activeMultiple]}: {hoveredMultiple?.value != null ? brFmt(hoveredMultiple.value) : "—"}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export function MultiplesChartLoading() {
  return (
    <div className="chart-loading">
      <div className="chart-loading-bar" />
      <div className="chart-loading-bar-sm" />
    </div>
  );
}
