// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, cleanup } from "@testing-library/react";
import { RevisitBanner } from "./RevisitBanner";

afterEach(cleanup);

const mockUseAuth = vi.fn();
const mockUseRevisitSchedules = vi.fn();
const mockUseVisits = vi.fn();

vi.mock("../hooks/useAuth", () => ({
  useAuth: () => mockUseAuth(),
}));

vi.mock("../hooks/useVisits", () => ({
  useRevisitSchedules: () => mockUseRevisitSchedules(),
  useVisits: (ticker?: string) => mockUseVisits(ticker),
}));

vi.mock("../i18n", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

function localToday(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}

const today = localToday();

function makeSchedule(overrides: Partial<{ next_revisit: string }> = {}) {
  return {
    id: 1,
    ticker: "VALE3",
    next_revisit: today,
    recurrence_days: null,
    share_token: "tok",
    notified_at: null,
    created_at: today,
    updated_at: today,
    ...overrides,
  };
}

describe("RevisitBanner", () => {
  beforeEach(() => {
    mockUseAuth.mockReturnValue({ isAuthenticated: true });
    mockUseVisits.mockReturnValue({
      markVisited: { mutate: vi.fn() },
      isVisitedToday: () => false,
    });
  });

  it("renders the banner when a revisit is due today and not yet visited", () => {
    mockUseRevisitSchedules.mockReturnValue({
      getScheduleForTicker: () => makeSchedule(),
    });

    render(<RevisitBanner ticker="VALE3" />);
    expect(document.querySelector(".revisit-banner")).not.toBeNull();
  });

  it("hides the banner when the company has been visited today", () => {
    mockUseRevisitSchedules.mockReturnValue({
      getScheduleForTicker: () => makeSchedule(),
    });
    mockUseVisits.mockReturnValue({
      markVisited: { mutate: vi.fn() },
      isVisitedToday: () => true,
    });

    render(<RevisitBanner ticker="VALE3" />);
    expect(document.querySelector(".revisit-banner")).toBeNull();
  });

  it("hides the banner when there is no schedule", () => {
    mockUseRevisitSchedules.mockReturnValue({
      getScheduleForTicker: () => undefined,
    });

    render(<RevisitBanner ticker="VALE3" />);
    expect(document.querySelector(".revisit-banner")).toBeNull();
  });

  it("hides the banner when the user is not authenticated", () => {
    mockUseAuth.mockReturnValue({ isAuthenticated: false });
    mockUseRevisitSchedules.mockReturnValue({
      getScheduleForTicker: () => makeSchedule(),
    });

    render(<RevisitBanner ticker="VALE3" />);
    expect(document.querySelector(".revisit-banner")).toBeNull();
  });

  it("hides the banner when the revisit is not due yet", () => {
    const future = new Date();
    future.setDate(future.getDate() + 7);
    mockUseRevisitSchedules.mockReturnValue({
      getScheduleForTicker: () => makeSchedule({
        next_revisit: `${future.getFullYear()}-${String(future.getMonth() + 1).padStart(2, "0")}-${String(future.getDate()).padStart(2, "0")}`,
      }),
    });

    render(<RevisitBanner ticker="VALE3" />);
    expect(document.querySelector(".revisit-banner")).toBeNull();
  });
});
