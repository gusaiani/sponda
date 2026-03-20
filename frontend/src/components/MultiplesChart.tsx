import { useCallback, useState } from "react";
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
function brFmt(n: number, decimals = 2): string {
  return n.toLocaleString("pt-BR", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
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

interface CompanyInfo {
  ticker: string;
  name: string;
  logo: string;
}

interface Props {
  data: MultiplesHistoryResult;
  company: CompanyInfo;
}

export function MultiplesChart({ data, company }: Props) {
  const [activeMultiple, setActiveMultiple] = useState<MultipleType>("pl");
  const [showPriceInfo, setShowPriceInfo] = useState(false);
  const [hoveredYear, setHoveredYear] = useState<number | null>(null);

  const multiplesData = data.multiples[activeMultiple];

  // Extract year from price chart hover: "mar/22" → 2022
  const handlePriceMouseMove = useCallback(
    (state: { activeLabel?: string | number }) => {
      if (!state.activeLabel) {
        setHoveredYear(null);
        return;
      }
      const parts = String(state.activeLabel).split("/");
      if (parts.length === 2) {
        const shortYear = parseInt(parts[1], 10);
        // Use previous year for the multiple (year-end data)
        const fullYear = (shortYear < 50 ? 2000 : 1900) + shortYear - 1;
        setHoveredYear(fullYear);
      }
    },
    [],
  );

  const handlePriceMouseLeave = useCallback(() => {
    setHoveredYear(null);
  }, []);

  if (!data.prices.length) {
    return (
      <div className="chart-container">
        <header className="pe10-card-header">
          {company.logo && (
            <img
              className="pe10-logo"
              src={company.logo}
              alt={`Logo ${company.name}`}
              onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
            />
          )}
          <h2 className="pe10-name">{company.name}</h2>
          <span className="pe10-ticker">{company.ticker}</span>
        </header>
        <div className="chart-empty">Dados históricos indisponíveis</div>
      </div>
    );
  }

  // Format dates for display: "2015-01-31" → "jan/15"
  const priceData = data.prices.map((p) => {
    const [y, m] = p.date.split("-");
    const monthNames = [
      "jan", "fev", "mar", "abr", "mai", "jun",
      "jul", "ago", "set", "out", "nov", "dez",
    ];
    const label = `${monthNames[parseInt(m, 10) - 1]}/${y.slice(2)}`;
    return { date: label, adjustedClose: p.adjustedClose };
  });

  // Show ~8 ticks on X axis regardless of data length
  const tickInterval = Math.max(1, Math.floor(priceData.length / 8));

  // Find the hovered year's data point in multiplesData for the ReferenceDot
  const hoveredMultiple = hoveredYear != null
    ? multiplesData.find((p) => p.year === hoveredYear)
    : null;

  return (
    <div className="chart-container">
      {/* Company header — same as PE10Card */}
      <header className="pe10-card-header">
        {company.logo && (
          <img
            className="pe10-logo"
            src={company.logo}
            alt={`Logo ${company.name}`}
            onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
          />
        )}
        <h2 className="pe10-name">{company.name}</h2>
        <span className="pe10-ticker">{company.ticker}</span>
      </header>

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
      <div className="chart-panel">
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
                label={{
                  value: `${hoveredMultiple.year}: ${brFmt(hoveredMultiple.value, 1)}`,
                  position: "top",
                  offset: 12,
                  fill: "#0f1f3d",
                  fontSize: 11,
                  fontFamily: "'Source Code Pro', monospace",
                }}
              />
            )}
          </LineChart>
        </ResponsiveContainer>
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
