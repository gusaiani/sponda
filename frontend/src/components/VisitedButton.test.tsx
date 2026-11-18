// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { VisitedButton } from "./VisitedButton";
import { rememberPostLoginReturn } from "../utils/postLoginReturn";

const mockUseAuth = vi.fn();
const markVisitedMutate = vi.fn();
const invalidateQueries = vi.fn(() => Promise.resolve());

vi.mock("../hooks/useAuth", () => ({
  useAuth: () => mockUseAuth(),
}));

vi.mock("../hooks/useVisits", () => ({
  useVisits: () => ({
    visits: [],
    isVisitedToday: () => false,
    markVisited: { mutate: markVisitedMutate },
  }),
  useRevisitSchedules: () => ({ getScheduleForTicker: () => undefined }),
}));

vi.mock("@tanstack/react-query", () => ({
  useQueryClient: () => ({ invalidateQueries }),
}));

vi.mock("../i18n", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
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

beforeEach(() => {
  window.sessionStorage.clear();
  markVisitedMutate.mockClear();
  invalidateQueries.mockClear();
});

afterEach(cleanup);

describe("VisitedButton after login", () => {
  it("resumes a mark-visited started before a Google login and opens the dialog", async () => {
    rememberPostLoginReturn("/pt/VALE3", { kind: "mark-visited", ticker: "VALE3" });
    mockUseAuth.mockReturnValue({ isAuthenticated: true });

    render(<VisitedButton ticker="VALE3" />);

    await waitFor(() => {
      expect(markVisitedMutate).toHaveBeenCalledWith({ ticker: "VALE3" });
    });
    expect(document.querySelector(".visited-expand")).not.toBeNull();
  });

  it("does not resume an action that was started on another company", () => {
    rememberPostLoginReturn("/pt/PETR4", { kind: "mark-visited", ticker: "PETR4" });
    mockUseAuth.mockReturnValue({ isAuthenticated: true });

    render(<VisitedButton ticker="VALE3" />);

    expect(markVisitedMutate).not.toHaveBeenCalled();
    expect(document.querySelector(".visited-expand")).toBeNull();
  });

  it("waits for the session before resuming the pending action", () => {
    rememberPostLoginReturn("/pt/VALE3", { kind: "mark-visited", ticker: "VALE3" });
    mockUseAuth.mockReturnValue({ isAuthenticated: false });

    render(<VisitedButton ticker="VALE3" />);

    expect(markVisitedMutate).not.toHaveBeenCalled();
    expect(window.sessionStorage.getItem("sponda.pendingAuthAction")).not.toBeNull();
  });

  it("hands the login modal the pending action for this company", () => {
    mockUseAuth.mockReturnValue({ isAuthenticated: false });

    render(<VisitedButton ticker="VALE3" />);
    fireEvent.click(screen.getByLabelText("visits.mark_visited"));

    const modal = screen.getByTestId("auth-modal");
    expect(JSON.parse(modal.dataset.pendingAction!)).toEqual({ kind: "mark-visited", ticker: "VALE3" });
  });

  it("marks the visit and opens the dialog after an email login in the modal", async () => {
    mockUseAuth.mockReturnValue({ isAuthenticated: false });

    render(<VisitedButton ticker="VALE3" />);
    fireEvent.click(screen.getByLabelText("visits.mark_visited"));

    mockUseAuth.mockReturnValue({ isAuthenticated: true });
    fireEvent.click(screen.getByText("finish login"));

    await waitFor(() => {
      expect(markVisitedMutate).toHaveBeenCalledWith({ ticker: "VALE3" });
    });
    await waitFor(() => {
      expect(document.querySelector(".visited-expand")).not.toBeNull();
    });
    expect(screen.queryByTestId("auth-modal")).toBeNull();
  });
});
