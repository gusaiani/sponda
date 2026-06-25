// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { ExpandButton, DetailedChart, IndicatorChartModal } from "./IndicatorChartModal";
import type { DataPoint } from "./MiniChart";

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
  const defaultProps = {
    title: "Current Price",
    currentValue: "R$ 12.00",
    data: series,
    onClose: vi.fn(),
  };

  it("renders the fullscreen overlay with the title and current value", () => {
    render(<IndicatorChartModal {...defaultProps} onClose={vi.fn()} />);
    expect(document.querySelector(".chart-fullscreen-overlay")).not.toBeNull();
    expect(screen.getByText("Current Price")).toBeTruthy();
    expect(screen.getByText("R$ 12.00")).toBeTruthy();
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
