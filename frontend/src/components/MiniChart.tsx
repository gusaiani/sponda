import { ResponsiveContainer, LineChart, Line, XAxis, Tooltip } from "recharts";

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

function defaultFormat(value: number): string {
  if (Math.abs(value) >= 1e9) return `${(value / 1e9).toFixed(1)}B`;
  if (Math.abs(value) >= 1e6) return `${(value / 1e6).toFixed(1)}M`;
  if (Math.abs(value) >= 1e3) return `${(value / 1e3).toFixed(1)}K`;
  return value.toFixed(2);
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
  formatValue = defaultFormat,
}: MiniChartProps) {
  if (data.length < 2) return null;

  // Add numeric index for x-axis positioning
  const indexed = data.map((d, i) => ({ ...d, idx: i }));

  // Build year boundary ticks from yearTick field
  const hasYearTicks = data[0]?.yearTick !== undefined;
  let ticks: number[] = [];

  if (hasYearTicks) {
    let lastTick = "";
    for (let i = 0; i < data.length; i++) {
      const tick = data[i].yearTick ?? "";
      if (tick !== lastTick) {
        ticks.push(i);
        lastTick = tick;
      }
    }
    // Thin out if too many
    if (ticks.length > 8) {
      const step = Math.ceil(ticks.length / 6);
      ticks = ticks.filter((_, i) => i % step === 0);
    }
  }

  const simpleMode = !hasYearTicks;
  const tickInterval = simpleMode && data.length > 6 ? 1 : 0;

  return (
    <div className="mini-chart">
      <ResponsiveContainer width="100%" height={height ?? "100%"}>
        <LineChart data={indexed} margin={{ top: 4, right: 4, left: 4, bottom: 0 }}>
          <XAxis
            dataKey="idx"
            type="number"
            domain={[0, data.length - 1]}
            tickLine={false}
            axisLine={false}
            tick={{ fontSize: 9, fill: "#5570a0" }}
            ticks={hasYearTicks ? ticks : undefined}
            interval={simpleMode ? tickInterval : undefined}
            tickFormatter={(idx: number) => {
              const point = data[idx];
              if (!point) return "";
              if (hasYearTicks) return point.yearTick ?? "";
              return String(point.label).slice(2);
            }}
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
