import { ResponsiveContainer, LineChart, Line, XAxis, Tooltip } from "recharts";

interface MiniChartProps {
  data: { year: number; value: number }[];
  color?: string;
  height?: number;
  formatValue?: (value: number) => string;
}

function defaultFormat(value: number): string {
  if (Math.abs(value) >= 1e9) return `${(value / 1e9).toFixed(1)}B`;
  if (Math.abs(value) >= 1e6) return `${(value / 1e6).toFixed(1)}M`;
  if (Math.abs(value) >= 1e3) return `${(value / 1e3).toFixed(1)}K`;
  return value.toFixed(2);
}

function MiniTooltipContent({ active, payload, formatValue }: {
  active?: boolean;
  payload?: { value: number; payload: { year: number } }[];
  formatValue: (value: number) => string;
}) {
  if (!active || !payload?.length) return null;
  const point = payload[0];
  return (
    <div className="mini-chart-tooltip">
      <span className="mini-chart-tooltip-year">{point.payload.year}</span>
      <span className="mini-chart-tooltip-value">{formatValue(point.value)}</span>
    </div>
  );
}

export function MiniChart({
  data,
  color = "#1e40af",
  height,
  formatValue = defaultFormat,
}: MiniChartProps) {
  if (data.length < 2) return null;

  const tickInterval = data.length > 6 ? 1 : 0;

  return (
    <div className="mini-chart">
      <ResponsiveContainer width="100%" height={height ?? "100%"}>
        <LineChart data={data} margin={{ top: 4, right: 4, left: 4, bottom: 0 }}>
          <XAxis
            dataKey="year"
            tickLine={false}
            axisLine={false}
            tick={{ fontSize: 9, fill: "#5570a0" }}
            interval={tickInterval}
            tickFormatter={(year: number) => String(year).slice(2)}
          />
          <Tooltip
            content={<MiniTooltipContent formatValue={formatValue} />}
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
