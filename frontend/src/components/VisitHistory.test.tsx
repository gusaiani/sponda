// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, cleanup, fireEvent, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { VisitHistory } from "./VisitHistory";
import { LanguageContext } from "../i18n";
import type { Locale } from "../i18n";

const mockUseAuth = vi.fn();
const mockUseVisits = vi.fn();

vi.mock("../hooks/useAuth", () => ({
  useAuth: () => mockUseAuth(),
}));

vi.mock("../hooks/useVisits", () => ({
  useVisits: (ticker?: string) => mockUseVisits(ticker),
}));

function makeVisit(id: number, visitedAt: string, note = "") {
  return { id, ticker: "VALE3", visited_at: visitedAt, note, created_at: `${visitedAt}T12:00:00Z` };
}

function renderInLocale(locale: Locale, children: ReactNode) {
  return render(
    <LanguageContext.Provider value={{ locale, setLocale: () => {} }}>{children}</LanguageContext.Provider>,
  );
}

beforeEach(() => {
  mockUseAuth.mockReturnValue({ isAuthenticated: true });
});

afterEach(cleanup);

describe("VisitHistory", () => {
  it("renders nothing for a visitor who is not logged in", () => {
    mockUseAuth.mockReturnValue({ isAuthenticated: false });
    mockUseVisits.mockReturnValue({ visits: [] });

    const { container } = renderInLocale("pt", <VisitHistory ticker="VALE3" />);

    expect(container.innerHTML).toBe("");
  });

  it("renders nothing when the company was never visited", () => {
    mockUseVisits.mockReturnValue({ visits: [] });

    const { container } = renderInLocale("pt", <VisitHistory ticker="VALE3" />);

    expect(container.innerHTML).toBe("");
  });

  it("asks for this company's visits only", () => {
    mockUseVisits.mockReturnValue({ visits: [] });

    renderInLocale("pt", <VisitHistory ticker="VALE3" />);

    expect(mockUseVisits).toHaveBeenCalledWith("VALE3");
  });

  it("shows the latest visit date in the Portuguese format", () => {
    mockUseVisits.mockReturnValue({
      visits: [makeVisit(1, "2026-09-01"), makeVisit(2, "2026-11-03")],
    });

    renderInLocale("pt", <VisitHistory ticker="VALE3" />);

    expect(screen.getByText("Última visita em 03/11/2026")).toBeTruthy();
  });

  it("shows the latest visit date in the English format", () => {
    mockUseVisits.mockReturnValue({ visits: [makeVisit(2, "2026-11-03")] });

    renderInLocale("en", <VisitHistory ticker="VALE3" />);

    expect(screen.getByText("Last visit on 11/03/2026")).toBeTruthy();
  });

  it("keeps the full list collapsed until asked", () => {
    mockUseVisits.mockReturnValue({
      visits: [makeVisit(2, "2026-11-03"), makeVisit(1, "2026-09-01")],
    });

    renderInLocale("pt", <VisitHistory ticker="VALE3" />);

    expect(document.querySelector(".visit-history-list")).toBeNull();
  });

  it("expands every visit in place, newest first, with notes", () => {
    mockUseVisits.mockReturnValue({
      visits: [makeVisit(1, "2026-09-01", "parece barata"), makeVisit(2, "2026-11-03")],
    });

    renderInLocale("pt", <VisitHistory ticker="VALE3" />);
    const toggle = screen.getByRole("button", { name: "Ver todas as visitas (2)" });
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(toggle);

    const items = document.querySelectorAll(".visit-history-item");
    expect(items).toHaveLength(2);
    expect(items[0].textContent).toContain("03/11/2026");
    expect(items[1].textContent).toContain("01/09/2026");
    expect(items[1].textContent).toContain("parece barata");
    expect(screen.getByRole("button", { name: "Ocultar visitas" }).getAttribute("aria-expanded")).toBe("true");
  });

  it("collapses the list again", () => {
    mockUseVisits.mockReturnValue({
      visits: [makeVisit(2, "2026-11-03"), makeVisit(1, "2026-09-01")],
    });

    renderInLocale("pt", <VisitHistory ticker="VALE3" />);
    fireEvent.click(screen.getByRole("button", { name: "Ver todas as visitas (2)" }));
    fireEvent.click(screen.getByRole("button", { name: "Ocultar visitas" }));

    expect(document.querySelector(".visit-history-list")).toBeNull();
  });

  it("offers the full list even when the only visit has no note", () => {
    mockUseVisits.mockReturnValue({ visits: [makeVisit(1, "2026-11-18")] });

    renderInLocale("pt", <VisitHistory ticker="ETER3" />);
    fireEvent.click(screen.getByRole("button", { name: "Ver todas as visitas (1)" }));

    const items = document.querySelectorAll(".visit-history-item");
    expect(items).toHaveLength(1);
    expect(items[0].textContent).toContain("18/11/2026");
  });
});
