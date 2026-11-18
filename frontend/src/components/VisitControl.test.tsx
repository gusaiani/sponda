// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { VisitControl } from "./VisitControl";
import { LanguageContext } from "../i18n";
import type { Locale } from "../i18n";
import { rememberPostLoginReturn } from "../utils/postLoginReturn";
import { localToday } from "../utils/format";

interface FakeVisit {
  id: number;
  ticker: string;
  visited_at: string;
  note: string;
  created_at: string;
}

const mockUseAuth = vi.fn();
const markVisitedMutate = vi.fn();
const invalidateQueries = vi.fn(() => Promise.resolve());
let fakeVisits: FakeVisit[] = [];
const requestedTickers: (string | undefined)[] = [];

vi.mock("../hooks/useAuth", () => ({
  useAuth: () => mockUseAuth(),
}));

vi.mock("../hooks/useVisits", () => ({
  useVisits: (ticker?: string) => {
    requestedTickers.push(ticker);
    return {
      visits: fakeVisits,
      isVisitedToday: (checkTicker: string) =>
        fakeVisits.some(
          (visit) => visit.ticker === checkTicker.toUpperCase() && visit.visited_at === localToday(),
        ),
      markVisited: { mutate: markVisitedMutate },
    };
  },
  useRevisitSchedules: () => ({ getScheduleForTicker: () => undefined }),
}));

vi.mock("@tanstack/react-query", () => ({
  useQueryClient: () => ({ invalidateQueries }),
}));

vi.mock("./AuthModal", () => ({
  AuthModal: ({
    onSuccess,
    pendingAction,
  }: {
    onSuccess: () => void;
    pendingAction?: { kind: string; ticker: string };
  }) => (
    <div data-testid="auth-modal" data-pending-action={JSON.stringify(pendingAction ?? null)}>
      <button type="button" onClick={onSuccess}>
        finish login
      </button>
    </div>
  ),
}));

function makeVisit(id: number, visitedAt: string, note = ""): FakeVisit {
  return { id, ticker: "VALE3", visited_at: visitedAt, note, created_at: `${visitedAt}T12:00:00Z` };
}

function renderControl(locale: Locale = "pt", children: ReactNode = <VisitControl ticker="VALE3" />) {
  return render(
    <LanguageContext.Provider value={{ locale, setLocale: () => {} }}>{children}</LanguageContext.Provider>,
  );
}

function capsule(): HTMLButtonElement {
  return document.querySelector(".visit-control-capsule") as HTMLButtonElement;
}

function popover(): HTMLElement | null {
  return document.querySelector(".visit-control-popover");
}

beforeEach(() => {
  window.sessionStorage.clear();
  markVisitedMutate.mockClear();
  invalidateQueries.mockClear();
  requestedTickers.length = 0;
  fakeVisits = [];
  mockUseAuth.mockReturnValue({ isAuthenticated: true });
});

afterEach(cleanup);

describe("VisitControl capsule", () => {
  it("asks for this company's visits only", () => {
    renderControl();

    expect(requestedTickers.every((ticker) => ticker === "VALE3")).toBe(true);
  });

  it("invites a first visit when the company was never visited", () => {
    renderControl();

    expect(capsule().textContent).toBe("Marcar como visitada");
    expect(capsule().classList.contains("visit-control-capsule--unvisited")).toBe(true);
  });

  it("invites a signed-out visitor too", () => {
    mockUseAuth.mockReturnValue({ isAuthenticated: false });

    renderControl();

    expect(capsule().textContent).toBe("Marcar como visitada");
  });

  it("says the company was visited today", () => {
    fakeVisits = [makeVisit(1, localToday())];

    renderControl();

    expect(capsule().textContent).toBe("Visitada hoje");
    expect(capsule().classList.contains("visit-control-capsule--today")).toBe(true);
  });

  it("shows the last visit date in the Portuguese format", () => {
    fakeVisits = [makeVisit(1, "2026-09-01"), makeVisit(2, "2026-11-03")];

    renderControl("pt");

    expect(capsule().textContent).toBe("Última visita em 03/11/2026");
    expect(capsule().classList.contains("visit-control-capsule--earlier")).toBe(true);
  });

  it("shows the last visit date in the English format", () => {
    fakeVisits = [makeVisit(2, "2026-11-03")];

    renderControl("en");

    expect(capsule().textContent).toBe("Last visit on 11/03/2026");
  });

  it("keeps an accessible name when the label is hidden on small screens", () => {
    fakeVisits = [makeVisit(2, "2026-11-03")];

    renderControl("pt");

    expect(capsule().getAttribute("aria-label")).toBe("Última visita em 03/11/2026");
  });
});

describe("VisitControl first visit", () => {
  it("marks the visit and opens the panel in one click", () => {
    renderControl();

    fireEvent.click(capsule());

    expect(markVisitedMutate).toHaveBeenCalledWith({ ticker: "VALE3" });
    expect(popover()).not.toBeNull();
    expect(document.querySelector(".visit-control-note")).not.toBeNull();
  });

  it("sends a signed-out visitor to the login modal with the pending action", () => {
    mockUseAuth.mockReturnValue({ isAuthenticated: false });

    renderControl();
    fireEvent.click(capsule());

    expect(markVisitedMutate).not.toHaveBeenCalled();
    const modal = screen.getByTestId("auth-modal");
    expect(JSON.parse(modal.dataset.pendingAction!)).toEqual({ kind: "mark-visited", ticker: "VALE3" });
  });

  it("marks the visit and opens the panel after an email login in the modal", async () => {
    mockUseAuth.mockReturnValue({ isAuthenticated: false });

    renderControl();
    fireEvent.click(capsule());
    mockUseAuth.mockReturnValue({ isAuthenticated: true });
    fireEvent.click(screen.getByText("finish login"));

    await waitFor(() => {
      expect(markVisitedMutate).toHaveBeenCalledWith({ ticker: "VALE3" });
    });
    await waitFor(() => {
      expect(popover()).not.toBeNull();
    });
    expect(screen.queryByTestId("auth-modal")).toBeNull();
  });
});

describe("VisitControl returning visit", () => {
  it("opens the history without marking a visit", () => {
    fakeVisits = [makeVisit(2, "2026-11-03"), makeVisit(1, "2026-09-01", "parece barata")];

    renderControl();
    fireEvent.click(capsule());

    expect(markVisitedMutate).not.toHaveBeenCalled();
    expect(capsule().getAttribute("aria-expanded")).toBe("true");
    const items = document.querySelectorAll(".visit-control-history-item");
    expect(items).toHaveLength(2);
    expect(items[0].textContent).toContain("03/11/2026");
    expect(items[1].textContent).toContain("01/09/2026");
    expect(items[1].textContent).toContain("parece barata");
  });

  it("lists visits newest first whatever order they arrive in", () => {
    fakeVisits = [makeVisit(1, "2026-09-01"), makeVisit(2, "2026-11-03")];

    renderControl();
    fireEvent.click(capsule());

    const items = document.querySelectorAll(".visit-control-history-item");
    expect(items[0].textContent).toContain("03/11/2026");
  });

  it("offers to mark today from the panel", () => {
    fakeVisits = [makeVisit(2, "2026-11-03")];

    renderControl();
    fireEvent.click(capsule());
    expect(document.querySelector(".visit-control-note")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Marcar como visitada hoje" }));

    expect(markVisitedMutate).toHaveBeenCalledWith({ ticker: "VALE3" });
    expect(document.querySelector(".visit-control-note")).not.toBeNull();
  });

  it("goes straight to the note and schedule when visited today", () => {
    fakeVisits = [makeVisit(3, localToday()), makeVisit(2, "2026-11-03")];

    renderControl();
    fireEvent.click(capsule());

    expect(markVisitedMutate).not.toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: "Marcar como visitada hoje" })).toBeNull();
    expect(document.querySelector(".visit-control-note")).not.toBeNull();
  });

  it("saves the note, revisit date and recurrence", () => {
    fakeVisits = [makeVisit(3, localToday())];

    renderControl();
    fireEvent.click(capsule());
    fireEvent.change(document.querySelector(".visit-control-note")!, { target: { value: " revisitar " } });
    fireEvent.change(document.querySelector("input.visit-control-date")!, { target: { value: "10012027" } });
    fireEvent.change(document.querySelector(".visit-control-recurrence")!, { target: { value: "90" } });
    fireEvent.click(screen.getByRole("button", { name: "Salvar" }));

    expect(markVisitedMutate).toHaveBeenCalledWith({
      ticker: "VALE3",
      note: "revisitar",
      next_revisit: "2027-01-10",
      recurrence_days: 90,
    });
    expect(popover()).toBeNull();
  });

  it("closes on Escape", () => {
    fakeVisits = [makeVisit(2, "2026-11-03")];

    renderControl();
    fireEvent.click(capsule());
    fireEvent.keyDown(document, { key: "Escape" });

    expect(popover()).toBeNull();
  });
});

describe("VisitControl after a Google login", () => {
  it("resumes the pending mark and opens the panel", async () => {
    rememberPostLoginReturn("/pt/VALE3", { kind: "mark-visited", ticker: "VALE3" });

    renderControl();

    await waitFor(() => {
      expect(markVisitedMutate).toHaveBeenCalledWith({ ticker: "VALE3" });
    });
    expect(popover()).not.toBeNull();
  });

  it("does not resume an action that was started on another company", () => {
    rememberPostLoginReturn("/pt/PETR4", { kind: "mark-visited", ticker: "PETR4" });

    renderControl();

    expect(markVisitedMutate).not.toHaveBeenCalled();
    expect(popover()).toBeNull();
  });

  it("waits for the session before resuming", () => {
    rememberPostLoginReturn("/pt/VALE3", { kind: "mark-visited", ticker: "VALE3" });
    mockUseAuth.mockReturnValue({ isAuthenticated: false });

    renderControl();

    expect(markVisitedMutate).not.toHaveBeenCalled();
    expect(window.sessionStorage.getItem("sponda.pendingAuthAction")).not.toBeNull();
  });
});
