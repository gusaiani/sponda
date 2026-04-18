// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import type { IndicatorAlert } from "../../../hooks/useAlerts";

const authState = { isAuthenticated: true, isLoading: false };
const alertsState: {
  alerts: IndicatorAlert[];
  isLoading: boolean;
  deleteAlert: { mutate: ReturnType<typeof vi.fn>; isPending: boolean };
} = {
  alerts: [],
  isLoading: false,
  deleteAlert: { mutate: vi.fn(), isPending: false },
};

vi.mock("../../../hooks/useAuth", () => ({
  useAuth: () => authState,
}));

vi.mock("../../../hooks/useAlerts", () => ({
  useAlerts: () => alertsState,
}));

vi.mock("../../../i18n", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    locale: "pt",
  }),
}));

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ locale: "pt" }),
}));

import AlertsPage from "./page";

function makeAlert(overrides: Partial<IndicatorAlert> = {}): IndicatorAlert {
  return {
    id: 1,
    ticker: "PETR4",
    indicator: "current_price",
    comparison: "lte",
    threshold: "30",
    active: true,
    triggered_at: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

beforeEach(() => {
  authState.isAuthenticated = true;
  authState.isLoading = false;
  alertsState.alerts = [];
  alertsState.isLoading = false;
  alertsState.deleteAlert.mutate = vi.fn();
  alertsState.deleteAlert.isPending = false;
  vi.spyOn(window, "confirm").mockReturnValue(true);
});

afterEach(cleanup);

describe("AlertsPage", () => {
  it("prompts unauthenticated users to log in", () => {
    authState.isAuthenticated = false;

    render(<AlertsPage />);

    expect(screen.getByText("alerts.must_login")).toBeTruthy();
  });

  it("shows empty-state copy when the user has no alerts", () => {
    render(<AlertsPage />);

    expect(screen.getByText("alerts.no_alerts")).toBeTruthy();
  });

  it("renders each alert with ticker, comparison operator and threshold", () => {
    alertsState.alerts = [
      makeAlert({ id: 1, ticker: "PETR4", comparison: "lte", threshold: "30" }),
      makeAlert({ id: 2, ticker: "VALE3", comparison: "gte", threshold: "90" }),
    ];

    render(<AlertsPage />);

    expect(screen.getByText("PETR4")).toBeTruthy();
    expect(screen.getByText("VALE3")).toBeTruthy();

    const rows = document.querySelectorAll(".alerts-page-item");
    expect(rows).toHaveLength(2);
    expect(rows[0].textContent).toContain("≤");
    expect(rows[0].textContent).toContain("30");
    expect(rows[1].textContent).toContain("≥");
    expect(rows[1].textContent).toContain("90");
  });

  it("marks triggered alerts with a badge", () => {
    alertsState.alerts = [
      makeAlert({ id: 1, triggered_at: "2026-02-01T10:00:00Z" }),
    ];

    render(<AlertsPage />);

    expect(screen.getByText("alerts.triggered_badge")).toBeTruthy();
  });

  it("calls deleteAlert.mutate with the alert id when the delete button is clicked", () => {
    alertsState.alerts = [makeAlert({ id: 42 })];

    render(<AlertsPage />);

    const deleteButton = screen.getByLabelText("alerts.delete");
    fireEvent.click(deleteButton);

    expect(alertsState.deleteAlert.mutate).toHaveBeenCalledWith(42);
  });
});
