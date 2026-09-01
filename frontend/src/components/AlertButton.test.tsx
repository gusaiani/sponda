// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/react";
import { AlertButton } from "./AlertButton";
import type { IndicatorAlert } from "../hooks/useAlerts";

afterEach(cleanup);

vi.mock("../hooks/useAuth", () => ({
  useAuth: () => ({ isAuthenticated: true }),
}));

const createAlertMutateAsync = vi.fn();
const alertsState: { alerts: IndicatorAlert[] } = { alerts: [] };

vi.mock("../hooks/useAlerts", () => ({
  useAlerts: () => ({
    alerts: alertsState.alerts,
    createAlert: { mutateAsync: createAlertMutateAsync, isPending: false },
    deleteAlert: { mutateAsync: vi.fn() },
  }),
}));

vi.mock("../i18n", () => ({
  useTranslation: () => ({
    t: (key: string, params?: Record<string, string | number>) =>
      params ? `${key}:${JSON.stringify(params)}` : key,
    locale: "pt",
  }),
}));

beforeEach(() => {
  alertsState.alerts = [];
  createAlertMutateAsync.mockReset();
  createAlertMutateAsync.mockResolvedValue(undefined);
});

function makeAlert(overrides: Partial<IndicatorAlert> = {}): IndicatorAlert {
  return {
    id: 1,
    ticker: "PETR4",
    indicator: "market_cap",
    comparison: "lte",
    threshold: "3000000000.000000",
    active: true,
    triggered_at: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function openPopover() {
  const trigger = screen.getByRole("button", { name: "alerts.create" });
  fireEvent.click(trigger);
}

function setComparison(value: "lte" | "gte") {
  const select = document.querySelector(".alert-popover-input") as HTMLSelectElement;
  fireEvent.change(select, { target: { value } });
}

function setThreshold(value: string) {
  const input = document.querySelectorAll(".alert-popover-input")[1] as HTMLInputElement;
  fireEvent.change(input, { target: { value } });
}

function getSaveButton(): HTMLButtonElement {
  return document.querySelector(".alert-popover-save") as HTMLButtonElement;
}

function getWarning(): HTMLElement | null {
  return document.querySelector(".alert-popover-warning");
}

function getThresholdLabel(): HTMLElement {
  return document.querySelectorAll(".alert-popover-label")[1] as HTMLElement;
}

describe("AlertButton already-triggered validation", () => {
  it("warns and disables save when lte threshold is already satisfied", () => {
    render(
      <AlertButton
        ticker="PETR4"
        indicator="current_price"
        indicatorLabel="Cotação"
        currentValue={46.25}
      />,
    );

    openPopover();
    setComparison("lte");
    setThreshold("90");

    const warning = getWarning();
    expect(warning).not.toBeNull();
    expect(warning!.textContent).toContain("alerts.already_triggered");
    expect(getSaveButton().disabled).toBe(true);
  });

  it("warns and disables save when gte threshold is already satisfied", () => {
    render(
      <AlertButton
        ticker="PETR4"
        indicator="current_price"
        indicatorLabel="Cotação"
        currentValue={46.25}
      />,
    );

    openPopover();
    setComparison("gte");
    setThreshold("10");

    expect(getWarning()).not.toBeNull();
    expect(getSaveButton().disabled).toBe(true);
  });

  it("does not warn and keeps save enabled when the threshold has not been reached", () => {
    render(
      <AlertButton
        ticker="PETR4"
        indicator="current_price"
        indicatorLabel="Cotação"
        currentValue={46.25}
      />,
    );

    openPopover();
    setComparison("lte");
    setThreshold("30");

    expect(getWarning()).toBeNull();
    expect(getSaveButton().disabled).toBe(false);
  });

  it("treats an exact boundary match as already triggered (<=)", () => {
    render(
      <AlertButton
        ticker="PETR4"
        indicator="debt_to_equity"
        indicatorLabel="Dívida/PL"
        currentValue={1.5}
      />,
    );

    openPopover();
    setComparison("lte");
    setThreshold("1.5");

    expect(getWarning()).not.toBeNull();
    expect(getSaveButton().disabled).toBe(true);
  });

  it("shows no warning when currentValue is null", () => {
    render(
      <AlertButton
        ticker="PETR4"
        indicator="peg"
        indicatorLabel="PEG"
        currentValue={null}
      />,
    );

    openPopover();
    setComparison("lte");
    setThreshold("1");

    expect(getWarning()).toBeNull();
    expect(getSaveButton().disabled).toBe(false);
  });

  it("shows no warning before the user enters a threshold", () => {
    render(
      <AlertButton
        ticker="PETR4"
        indicator="current_price"
        indicatorLabel="Cotação"
        currentValue={46.25}
      />,
    );

    openPopover();

    expect(getWarning()).toBeNull();
  });
});

describe("AlertButton market cap thresholds in millions", () => {
  const FOUR_POINT_TWO_BILLION = 4_230_000_000;

  it("labels the market cap threshold in millions of the ticker's currency", () => {
    render(
      <AlertButton
        ticker="PETR4"
        indicator="market_cap"
        indicatorLabel="Market Cap"
        currentValue={FOUR_POINT_TWO_BILLION}
      />,
    );

    openPopover();

    expect(getThresholdLabel().textContent).toBe('alerts.threshold_millions:{"currency":"R$"}');
  });

  it("uses the dollar sign for a US ticker", () => {
    render(
      <AlertButton
        ticker="AAPL"
        indicator="market_cap"
        indicatorLabel="Market Cap"
        currentValue={FOUR_POINT_TWO_BILLION}
      />,
    );

    openPopover();

    expect(getThresholdLabel().textContent).toBe('alerts.threshold_millions:{"currency":"$"}');
  });

  it("keeps the plain threshold label for other indicators", () => {
    render(
      <AlertButton
        ticker="PETR4"
        indicator="current_price"
        indicatorLabel="Cotação"
        currentValue={46.25}
      />,
    );

    openPopover();

    expect(getThresholdLabel().textContent).toBe("alerts.threshold");
  });

  it("compares a threshold entered in millions against the raw current value", () => {
    render(
      <AlertButton
        ticker="PETR4"
        indicator="market_cap"
        indicatorLabel="Market Cap"
        currentValue={FOUR_POINT_TWO_BILLION}
      />,
    );

    openPopover();
    setComparison("lte");
    setThreshold("3000");
    expect(getWarning()).toBeNull();
    expect(getSaveButton().disabled).toBe(false);

    setThreshold("5000");
    expect(getWarning()).not.toBeNull();
    expect(getSaveButton().disabled).toBe(true);
  });

  it("saves the threshold scaled from millions into raw currency units", async () => {
    render(
      <AlertButton
        ticker="PETR4"
        indicator="market_cap"
        indicatorLabel="Market Cap"
        currentValue={FOUR_POINT_TWO_BILLION}
      />,
    );

    openPopover();
    setComparison("lte");
    setThreshold("3000");
    fireEvent.click(getSaveButton());

    await waitFor(() => expect(createAlertMutateAsync).toHaveBeenCalledTimes(1));
    expect(createAlertMutateAsync).toHaveBeenCalledWith({
      ticker: "PETR4",
      indicator: "market_cap",
      comparison: "lte",
      threshold: "3000000000",
    });
  });

  it("lists existing market cap alerts in millions", () => {
    alertsState.alerts = [makeAlert({ threshold: "3000000000.000000" })];

    render(
      <AlertButton
        ticker="PETR4"
        indicator="market_cap"
        indicatorLabel="Market Cap"
        currentValue={FOUR_POINT_TWO_BILLION}
      />,
    );

    openPopover();

    const item = document.querySelector(".alert-popover-item-text") as HTMLElement;
    expect(item.textContent).toContain("R$ 3.000M");
    expect(item.textContent).not.toContain("3000000000");
  });

  it("lists existing price alerts with two decimals and no trailing zeros", () => {
    alertsState.alerts = [
      makeAlert({ indicator: "current_price", threshold: "30.000000" }),
    ];

    render(
      <AlertButton
        ticker="PETR4"
        indicator="current_price"
        indicatorLabel="Cotação"
        currentValue={46.25}
      />,
    );

    openPopover();

    const item = document.querySelector(".alert-popover-item-text") as HTMLElement;
    expect(item.textContent).toContain("R$ 30,00");
  });
});
