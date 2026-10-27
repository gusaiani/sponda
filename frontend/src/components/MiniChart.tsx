import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip } from "recharts";
import { useTranslation } from "../i18n";
import { formatNumber } from "../utils/format";
import {
  computeSparklineValueDomain,
  findYearBoundaryTicks,
  hasVisibleYearBoundary,
} from "../utils/sparklineScale";

/** Room for the stroke and the hover dot (radius 3 + 1.5 border). */
const LINE_EDGE_INSET = 5;
/** Tall enough for the 9px year labels and nothing more. */
const YEAR_AXIS_HEIGHT = 14;

interface DataPoint {
  label: string;
  value: number;
  yearTick?: string;
}

interface MiniChartProps {
  data: DataPoint[];
  color?: string;
  height?: number;
  formatValue?: (value: number) => string;
}

function makeDefaultFormat(locale: string) {
  return (value: number): string => {
    if (Math.abs(value) >= 1e9) return `${formatNumber(value / 1e9, 1, locale)}B`;
    if (Math.abs(value) >= 1e6) return `${formatNumber(value / 1e6, 1, locale)}M`;
    if (Math.abs(value) >= 1e3) return `${formatNumber(value / 1e3, 1, locale)}K`;
    return formatNumber(value, 2, locale);
  };
}

function MiniTooltipContent({ active, payload, formatValue }: {
  active?: boolean;
  payload?: { value: number; payload: DataPoint }[];
  formatValue: (value: number) => string;
}) {
  if (!active || !payload?.length) return null;
  const point = payload[0];
  return (
    <div className="mini-chart-tooltip">
      <span className="mini-chart-tooltip-year">{point.payload.label}</span>
      <span className="mini-chart-tooltip-value">{formatValue(point.value)}</span>
    </div>
  );
}

export type { DataPoint };

export function MiniChart({
  data,
  color = "#1e40af",
  height,
  formatValue,
}: MiniChartProps) {
  const { locale } = useTranslation();
  const effectiveFormatValue = formatValue ?? makeDefaultFormat(locale);
  if (data.length < 2) return null;

  const indexedPoints = data.map((point, index) => ({ ...point, index }));
  const valueDomain = computeSparklineValueDomain(data.map((point) => point.value));

  const hasYearTicks = data[0]?.yearTick !== undefined;
  const yearTicks = hasYearTicks ? findYearBoundaryTicks(data) : [];
  const showTimeAxis = !hasYearTicks || hasVisibleYearBoundary(yearTicks);

  const simpleMode = !hasYearTicks;
  const tickInterval = simpleMode && data.length > 6 ? 1 : 0;

  return (
    <div className="mini-chart">
      <ResponsiveContainer width="100%" height={height ?? "100%"}>
        <LineChart
          data={indexedPoints}
          margin={{ top: 0, right: 4, left: 4, bottom: 0 }}
        >
          <YAxis
            hide
            domain={valueDomain}
            padding={{ top: LINE_EDGE_INSET, bottom: LINE_EDGE_INSET }}
          />
          <XAxis
            dataKey="index"
            hide={!showTimeAxis}
            height={YEAR_AXIS_HEIGHT}
            type="number"
            domain={[0, data.length - 1]}
            tickLine={false}
            axisLine={false}
            tick={{ fontSize: 9, fill: "#5570a0" }}
            ticks={hasYearTicks ? yearTicks : undefined}
            interval={simpleMode ? tickInterval : undefined}
            tickFormatter={(pointIndex: number) => {
              const point = data[pointIndex];
              if (!point) return "";
              if (hasYearTicks) return point.yearTick ?? "";
              return String(point.label).slice(2);
            }}
          />
          <Tooltip
            content={<MiniTooltipContent formatValue={effectiveFormatValue} />}
            cursor={{ stroke: "#d0daea", strokeWidth: 1 }}
          />
          <Line
            type="monotone"
            dataKey="value"
            stroke={color}
            strokeWidth={1.5}
            dot={false}
            activeDot={{ r: 3, fill: color, stroke: "#fff", strokeWidth: 1.5 }}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
