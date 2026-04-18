// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { AlertButton } from "./AlertButton";

afterEach(cleanup);

vi.mock("../hooks/useAuth", () => ({
  useAuth: () => ({ isAuthenticated: true }),
}));

vi.mock("../hooks/useAlerts", () => ({
  useAlerts: () => ({
    alerts: [],
    createAlert: { mutateAsync: vi.fn(), isPending: false },
    deleteAlert: { mutateAsync: vi.fn() },
  }),
}));

vi.mock("../i18n", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    locale: "pt",
  }),
}));

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
