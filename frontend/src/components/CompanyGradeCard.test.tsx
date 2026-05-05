// @vitest-environment jsdom
import { describe, it, expect, afterEach, vi } from "vitest";
import { render, cleanup, fireEvent } from "@testing-library/react";
import { CompanyGradeCard } from "./CompanyGradeCard";

afterEach(cleanup);

const mockUseLearningMode = vi.fn();

vi.mock("../learning", () => ({
  useLearningMode: () => mockUseLearningMode(),
}));

vi.mock("../i18n", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    locale: "en",
  }),
}));

describe("CompanyGradeCard", () => {
  it("renders nothing when learning mode is disabled", () => {
    mockUseLearningMode.mockReturnValue({ enabled: false, available: true });
    const { container } = render(<CompanyGradeCard ratings={{ overall: 4 }} />);
    expect(container.querySelector(".company-grade-card")).toBeNull();
  });

  it("renders the grade numeral when an overall is provided", () => {
    mockUseLearningMode.mockReturnValue({ enabled: true, available: true });
    const { container } = render(<CompanyGradeCard ratings={{ overall: 4 }} />);
    const card = container.querySelector(".company-grade-card");
    expect(card).not.toBeNull();
    expect(card?.textContent).toContain("4");
  });

  it("renders an empty-state when overall is null", () => {
    mockUseLearningMode.mockReturnValue({ enabled: true, available: true });
    const { container } = render(<CompanyGradeCard ratings={{ overall: null }} />);
    expect(container.querySelector(".company-grade-card")).not.toBeNull();
    expect(container.querySelector(".company-grade-card-empty")).not.toBeNull();
  });

  it("applies tier-specific class for color coding", () => {
    mockUseLearningMode.mockReturnValue({ enabled: true, available: true });
    const { container } = render(<CompanyGradeCard ratings={{ overall: 5 }} />);
    expect(container.querySelector(".company-grade-card-tier-5")).not.toBeNull();
  });

  it("renders the Avaliação prefix inside the trigger", () => {
    mockUseLearningMode.mockReturnValue({ enabled: true, available: true });
    const { container } = render(<CompanyGradeCard ratings={{ overall: 3 }} />);
    expect(container.querySelector(".company-grade-card-prefix")).not.toBeNull();
  });

  it("portals the tooltip into document.body when hovered", () => {
    mockUseLearningMode.mockReturnValue({ enabled: true, available: true });
    const { container } = render(
      <CompanyGradeCard
        ratings={{ overall: 3, pe10: 4, pfcf10: 2, debtToEquity: 3 }}
      />,
    );
    const trigger = container.querySelector(".company-grade-card") as HTMLElement;
    fireEvent.mouseEnter(trigger);
    const tooltip = document.body.querySelector(".company-grade-card-tooltip");
    expect(tooltip).not.toBeNull();
    const rows = document.body.querySelectorAll(".company-grade-card-tooltip-row");
    expect(rows.length).toBe(3);
  });

  it("hides the tooltip on mouse leave", () => {
    mockUseLearningMode.mockReturnValue({ enabled: true, available: true });
    const { container } = render(
      <CompanyGradeCard ratings={{ overall: 3, pe10: 4 }} />,
    );
    const trigger = container.querySelector(".company-grade-card") as HTMLElement;
    fireEvent.mouseEnter(trigger);
    expect(document.body.querySelector(".company-grade-card-tooltip")).not.toBeNull();
    fireEvent.mouseLeave(trigger);
    expect(document.body.querySelector(".company-grade-card-tooltip")).toBeNull();
  });
});
