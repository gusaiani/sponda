// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, cleanup, fireEvent, waitFor } from "@testing-library/react";
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

function makeSchedule(overrides: Partial<{ next_revisit: string; recurrence_days?: number | null }> = {}) {
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
      updateSchedule: { mutate: vi.fn() },
      deleteSchedule: { mutate: vi.fn() },
    });

    render(<RevisitBanner ticker="VALE3" />);
    expect(document.querySelector(".revisit-banner")).not.toBeNull();
  });

  it("hides the banner when the company has been visited today", () => {
    mockUseRevisitSchedules.mockReturnValue({
      getScheduleForTicker: () => makeSchedule(),
      updateSchedule: { mutate: vi.fn() },
      deleteSchedule: { mutate: vi.fn() },
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
      updateSchedule: { mutate: vi.fn() },
      deleteSchedule: { mutate: vi.fn() },
    });

    render(<RevisitBanner ticker="VALE3" />);
    expect(document.querySelector(".revisit-banner")).toBeNull();
  });

  it("hides the banner when the user is not authenticated", () => {
    mockUseAuth.mockReturnValue({ isAuthenticated: false });
    mockUseRevisitSchedules.mockReturnValue({
      getScheduleForTicker: () => makeSchedule(),
      updateSchedule: { mutate: vi.fn() },
      deleteSchedule: { mutate: vi.fn() },
    });

    render(<RevisitBanner ticker="VALE3" />);
    expect(document.querySelector(".revisit-banner")).toBeNull();
  });

  it("hides the banner when the revisit is not due yet", () => {
    const future = new Date();
    future.setDate(future.getDate() + 7);
    const futureDate = `${future.getFullYear()}-${String(future.getMonth() + 1).padStart(2, "0")}-${String(future.getDate()).padStart(2, "0")}`;

    mockUseRevisitSchedules.mockReturnValue({
      getScheduleForTicker: () => makeSchedule({ next_revisit: futureDate }),
      updateSchedule: { mutate: vi.fn() },
      deleteSchedule: { mutate: vi.fn() },
    });

    render(<RevisitBanner ticker="VALE3" />);
    expect(document.querySelector(".revisit-banner")).toBeNull();
  });

  it("renders both Mark as visited and Change settings buttons", () => {
    mockUseRevisitSchedules.mockReturnValue({
      getScheduleForTicker: () => makeSchedule(),
      updateSchedule: { mutate: vi.fn() },
      deleteSchedule: { mutate: vi.fn() },
    });

    render(<RevisitBanner ticker="VALE3" />);
    expect(document.querySelector(".revisit-banner-mark-visited")).not.toBeNull();
    expect(document.querySelector(".revisit-banner-change-settings")).not.toBeNull();
  });

  it("expands form when Mark as visited button is clicked", () => {
    mockUseRevisitSchedules.mockReturnValue({
      getScheduleForTicker: () => makeSchedule(),
      updateSchedule: { mutate: vi.fn() },
      deleteSchedule: { mutate: vi.fn() },
    });

    render(<RevisitBanner ticker="VALE3" />);
    const markVisitedButton = document.querySelector(".revisit-banner-mark-visited") as HTMLButtonElement;

    fireEvent.click(markVisitedButton);

    expect(document.querySelector(".revisit-banner-expanded")).not.toBeNull();
    expect(document.querySelector(".revisit-banner-note-input")).not.toBeNull();
    expect(document.querySelector(".revisit-banner-recurrence-select")).not.toBeNull();
  });

  it("calls markVisited.mutate when Save button is clicked in mark mode", () => {
    const markVisitedMock = vi.fn();

    mockUseRevisitSchedules.mockReturnValue({
      getScheduleForTicker: () => makeSchedule(),
      updateSchedule: { mutate: vi.fn() },
      deleteSchedule: { mutate: vi.fn() },
    });
    mockUseVisits.mockReturnValue({
      markVisited: { mutate: markVisitedMock },
      isVisitedToday: () => false,
    });

    render(<RevisitBanner ticker="VALE3" />);
    const markVisitedButton = document.querySelector(".revisit-banner-mark-visited") as HTMLButtonElement;

    fireEvent.click(markVisitedButton);

    const saveButton = document.querySelector(".revisit-banner-save") as HTMLButtonElement;
    fireEvent.click(saveButton);

    expect(markVisitedMock).toHaveBeenCalledWith({ ticker: "VALE3" });
  });

  it("expands settings form with Cancel recurrence when schedule is recurring", () => {
    mockUseRevisitSchedules.mockReturnValue({
      getScheduleForTicker: () => makeSchedule({ recurrence_days: 90 }),
      updateSchedule: { mutate: vi.fn() },
      deleteSchedule: { mutate: vi.fn() },
    });

    render(<RevisitBanner ticker="VALE3" />);
    const changeSettingsButton = document.querySelector(".revisit-banner-change-settings") as HTMLButtonElement;

    fireEvent.click(changeSettingsButton);

    expect(document.querySelector(".revisit-banner-expanded")).not.toBeNull();
    expect(document.querySelector(".revisit-banner-cancel-recurrence")).not.toBeNull();
  });

  it("hides Cancel recurrence button when schedule has no recurrence", () => {
    mockUseRevisitSchedules.mockReturnValue({
      getScheduleForTicker: () => makeSchedule({ recurrence_days: null }),
      updateSchedule: { mutate: vi.fn() },
      deleteSchedule: { mutate: vi.fn() },
    });

    render(<RevisitBanner ticker="VALE3" />);
    const changeSettingsButton = document.querySelector(".revisit-banner-change-settings") as HTMLButtonElement;

    fireEvent.click(changeSettingsButton);

    expect(document.querySelector(".revisit-banner-expanded")).not.toBeNull();
    expect(document.querySelector(".revisit-banner-cancel-recurrence")).toBeNull();
  });

  it("calls deleteSchedule when cancel recurrence is confirmed", () => {
    const deleteScheduleMock = vi.fn();

    mockUseRevisitSchedules.mockReturnValue({
      getScheduleForTicker: () => makeSchedule({ recurrence_days: 90 }),
      updateSchedule: { mutate: vi.fn() },
      deleteSchedule: { mutate: deleteScheduleMock },
    });

    render(<RevisitBanner ticker="VALE3" />);
    const changeSettingsButton = document.querySelector(".revisit-banner-change-settings") as HTMLButtonElement;

    fireEvent.click(changeSettingsButton);

    const cancelRecurrenceButton = document.querySelector(".revisit-banner-cancel-recurrence") as HTMLButtonElement;
    fireEvent.click(cancelRecurrenceButton);

    const confirmButton = document.querySelector(".revisit-banner-cancel-recurrence-confirm") as HTMLButtonElement;
    fireEvent.click(confirmButton);

    expect(deleteScheduleMock).toHaveBeenCalledWith(1);
  });

  it("shows overdue message for past due dates", () => {
    const past = new Date();
    past.setDate(past.getDate() - 5);
    const pastDate = `${past.getFullYear()}-${String(past.getMonth() + 1).padStart(2, "0")}-${String(past.getDate()).padStart(2, "0")}`;

    mockUseRevisitSchedules.mockReturnValue({
      getScheduleForTicker: () => makeSchedule({ next_revisit: pastDate }),
      updateSchedule: { mutate: vi.fn() },
      deleteSchedule: { mutate: vi.fn() },
    });

    render(<RevisitBanner ticker="VALE3" />);
    const banner = document.querySelector(".revisit-banner");
    expect(banner?.classList.contains("revisit-banner-overdue")).toBe(true);
  });
});
