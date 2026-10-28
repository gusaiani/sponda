// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from "vitest";
import { cloneElement, type ReactElement } from "react";
import { render, cleanup, waitFor } from "@testing-library/react";
import { IndicatorChartModal } from "./IndicatorChartModal";
import type { DataPoint } from "./MiniChart";

vi.mock("../i18n", () => ({
  useTranslation: () => ({ t: (key: string) => key, locale: "en" }),
}));
vi.mock("../hooks/useComparisonSeries", () => ({
  useComparisonSeries: () => [],
}));
vi.mock("../hooks/useFxSeries", () => ({
  useFxSeriesMany: () => ({}),
}));
vi.mock("../hooks/useTickerSearch", () => ({
  useTickerSearch: () => ({ results: [] }),
}));
// ResponsiveContainer measures its parent, which jsdom reports as 0 x 0, so
// nothing would render. A fixed size lets the axes lay out their ticks.
vi.mock("recharts", async (importOriginal) => {
  const recharts = await importOriginal<typeof import("recharts")>();
  return {
    ...recharts,
    ResponsiveContainer: ({ children }: { children: ReactElement<{ width?: number; height?: number }> }) =>
      cloneElement(children, { width: 1600, height: 700 }),
  };
});

afterEach(cleanup);

const CHART_TEXT_SELECTOR = ".chart-fullscreen-body text";

/** One closing price per weekday of 2026 up to late October, like DEXP3's 1-year view. */
function dailyPricesThisYear(): DataPoint[] {
  const points: DataPoint[] = [];
  const start = Date.parse("2026-01-02T00:00:00Z");
  const end = Date.parse("2026-10-27T00:00:00Z");
  let dayNumber = 0;
  for (let timestamp = start; timestamp <= end; timestamp += 86_400_000) {
    const weekday = new Date(timestamp).getUTCDay();
    if (weekday === 0 || weekday === 6) continue;
    const label = new Date(timestamp).toISOString().slice(0, 10);
    points.push({ label, value: 7.1 + 0.35 * Math.sin(dayNumber / 20), yearTick: "26" });
    dayNumber += 1;
  }
  return points;
}

function renderPriceChart(points: DataPoint[]) {
  return render(
    <IndicatorChartModal
      indicatorLabel="Current Price"
      metricId="current-price"
      primary={{ ticker: "DEXP3", name: "Dexxos", currency: "BRL", points }}
      years={1}
      maxYears={15}
      onYearsChange={vi.fn()}
      onClose={vi.fn()}
    />,
  );
}

async function axisLabels(): Promise<string[]> {
  await waitFor(() => {
    expect(document.querySelectorAll(CHART_TEXT_SELECTOR).length).toBeGreaterThan(0);
  });
  return [...document.querySelectorAll(CHART_TEXT_SELECTOR)].map((node) => node.textContent ?? "");
}

describe("IndicatorChartModal axes", () => {
  it("fits the value axis to the series instead of starting it at zero", async () => {
    renderPriceChart(dailyPricesThisYear());
    const valueLabels = (await axisLabels())
      .map((label) => Number(label.replace(/,/g, "")))
      .filter(Number.isFinite);
    expect(valueLabels.length).toBeGreaterThan(1);
    expect(Math.min(...valueLabels)).toBeGreaterThan(6);
    expect(Math.max(...valueLabels)).toBeLessThan(8);
  });

  it("labels every month on a one-year window", async () => {
    renderPriceChart(dailyPricesThisYear());
    const labels = await axisLabels();
    for (const month of ["Jan/26", "Apr/26", "Jul/26", "Oct/26"]) {
      expect(labels).toContain(month);
    }
  });
});
