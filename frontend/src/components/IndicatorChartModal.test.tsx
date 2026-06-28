// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { ExpandButton, DetailedChart, IndicatorChartModal } from "./IndicatorChartModal";
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

afterEach(cleanup);

const series: DataPoint[] = [
  { label: "2022", value: 10, yearTick: "22" },
  { label: "2023", value: 14, yearTick: "23" },
  { label: "2024", value: 12, yearTick: "24" },
];

describe("ExpandButton", () => {
  it("renders a button with the provided aria-label", () => {
    render(<ExpandButton label="View chart in detail" onClick={() => {}} />);
    const button = screen.getByRole("button", { name: "View chart in detail" });
    expect(button.classList.contains("expand-btn")).toBe(true);
  });

  it("calls onClick when clicked", () => {
    const onClick = vi.fn();
    render(<ExpandButton label="Expand" onClick={onClick} />);
    fireEvent.click(screen.getByRole("button", { name: "Expand" }));
    expect(onClick).toHaveBeenCalledTimes(1);
  });
});

describe("DetailedChart", () => {
  it("renders a chart container when given at least two points", () => {
    const { container } = render(<DetailedChart data={series} />);
    expect(container.querySelector(".detailed-chart")).not.toBeNull();
  });

  it("renders nothing when given fewer than two points", () => {
    const { container } = render(<DetailedChart data={[series[0]]} />);
    expect(container.querySelector(".detailed-chart")).toBeNull();
  });
});

describe("IndicatorChartModal", () => {
  const primary = { ticker: "ACME3", name: "ACME", currency: "BRL", points: series };
  const defaultProps = {
    indicatorLabel: "Current Price",
    metricId: "current-price",
    primary,
    years: 10,
    maxYears: 20,
    onYearsChange: vi.fn(),
    onClose: vi.fn(),
  };

  it("renders the fullscreen overlay with the indicator and company in the title", () => {
    render(<IndicatorChartModal {...defaultProps} onClose={vi.fn()} />);
    expect(document.querySelector(".chart-fullscreen-overlay")).not.toBeNull();
    expect(screen.getByText("Current Price — ACME")).toBeTruthy();
  });

  it("renders the term slider and an add-company input", () => {
    render(<IndicatorChartModal {...defaultProps} onClose={vi.fn()} />);
    expect(document.querySelector(".years-slider")).not.toBeNull();
    expect(document.querySelector(".compare-add-input")).not.toBeNull();
  });

  it("shows the primary company in the legend without a remove button", () => {
    render(<IndicatorChartModal {...defaultProps} onClose={vi.fn()} />);
    expect(screen.getByText("ACME")).toBeTruthy();
    expect(document.querySelector(".chart-legend-remove")).toBeNull();
  });

  it("does not show the scale toggle for a single company", () => {
    render(<IndicatorChartModal {...defaultProps} onClose={vi.fn()} />);
    expect(document.querySelector(".chart-scale-toggle")).toBeNull();
  });

  it("calls onClose when the close button is clicked", () => {
    const onClose = vi.fn();
    render(<IndicatorChartModal {...defaultProps} onClose={onClose} />);
    fireEvent.click(screen.getByRole("button", { name: /close/i }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("calls onClose when Escape is pressed", () => {
    const onClose = vi.fn();
    render(<IndicatorChartModal {...defaultProps} onClose={onClose} />);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("calls onClose when the backdrop is clicked", () => {
    const onClose = vi.fn();
    render(<IndicatorChartModal {...defaultProps} onClose={onClose} />);
    fireEvent.click(document.querySelector(".chart-fullscreen-overlay")!);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("does not call onClose when the content panel is clicked", () => {
    const onClose = vi.fn();
    render(<IndicatorChartModal {...defaultProps} onClose={onClose} />);
    fireEvent.click(document.querySelector(".chart-fullscreen-content")!);
    expect(onClose).not.toHaveBeenCalled();
  });
});
