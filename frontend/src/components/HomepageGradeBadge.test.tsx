// @vitest-environment jsdom
import { describe, it, expect, afterEach, vi } from "vitest";
import { render, cleanup, fireEvent } from "@testing-library/react";
import { HomepageGradeBadge } from "./HomepageGradeBadge";

afterEach(cleanup);

const mockUseLearningMode = vi.fn();

vi.mock("../learning", () => ({
  useLearningMode: () => mockUseLearningMode(),
}));

vi.mock("../i18n", () => ({
  useTranslation: () => ({
    t: (key: string) => {
      // Mirror real strings that carry placeholders so component code that
      // performs `.replace("{years}", …)` actually has something to replace.
      if (key === "learning.grade.tooltip.term") return "Term: {years} years";
      if (key === "learning.grade.tooltip.intro") return "Mean of {count} indicators.";
      return key;
    },
    locale: "en",
  }),
}));

describe("HomepageGradeBadge", () => {
  it("renders nothing when learning mode is disabled", () => {
    mockUseLearningMode.mockReturnValue({ enabled: false, available: true });
    const { container } = render(<HomepageGradeBadge ratings={{ overall: 4 }} />);
    expect(container.querySelector(".homepage-grade-badge")).toBeNull();
  });

  it("renders nothing when overall is null", () => {
    mockUseLearningMode.mockReturnValue({ enabled: true, available: true });
    const { container } = render(<HomepageGradeBadge ratings={{ overall: null }} />);
    expect(container.querySelector(".homepage-grade-badge")).toBeNull();
  });

  it("renders nothing when ratings is missing", () => {
    mockUseLearningMode.mockReturnValue({ enabled: true, available: true });
    const { container } = render(<HomepageGradeBadge ratings={null} />);
    expect(container.querySelector(".homepage-grade-badge")).toBeNull();
  });

  it("renders the rounded grade numeral", () => {
    mockUseLearningMode.mockReturnValue({ enabled: true, available: true });
    const { container } = render(<HomepageGradeBadge ratings={{ overall: 4 }} />);
    const badge = container.querySelector(".homepage-grade-badge");
    expect(badge).not.toBeNull();
    expect(badge?.textContent).toContain("4");
  });

  it("applies tier-specific class for color coding", () => {
    mockUseLearningMode.mockReturnValue({ enabled: true, available: true });
    const { container } = render(<HomepageGradeBadge ratings={{ overall: 5 }} />);
    expect(container.querySelector(".homepage-grade-badge-tier-5")).not.toBeNull();
  });

  it("portals the breakdown tooltip into document.body when hovered", () => {
    mockUseLearningMode.mockReturnValue({ enabled: true, available: true });
    const { container } = render(
      <HomepageGradeBadge
        ratings={{ overall: 3, pe10: 4, pfcf10: 2, debtToEquity: 3 }}
      />,
    );
    const trigger = container.querySelector(".homepage-grade-badge") as HTMLElement;
    fireEvent.mouseEnter(trigger);
    const tooltip = document.body.querySelector(".homepage-grade-badge-tooltip");
    expect(tooltip).not.toBeNull();
    const rows = document.body.querySelectorAll(".homepage-grade-badge-tooltip-row");
    expect(rows.length).toBe(3);
  });

  it("hides the tooltip on mouse leave", () => {
    mockUseLearningMode.mockReturnValue({ enabled: true, available: true });
    const { container } = render(
      <HomepageGradeBadge ratings={{ overall: 3, pe10: 4 }} />,
    );
    const trigger = container.querySelector(".homepage-grade-badge") as HTMLElement;
    fireEvent.mouseEnter(trigger);
    expect(document.body.querySelector(".homepage-grade-badge-tooltip")).not.toBeNull();
    fireEvent.mouseLeave(trigger);
    expect(document.body.querySelector(".homepage-grade-badge-tooltip")).toBeNull();
  });

  it("shows the derivation term inside the tooltip when years is provided", () => {
    mockUseLearningMode.mockReturnValue({ enabled: true, available: true });
    const { container } = render(
      <HomepageGradeBadge ratings={{ overall: 3, pe10: 4 }} years={10} />,
    );
    const trigger = container.querySelector(".homepage-grade-badge") as HTMLElement;
    fireEvent.mouseEnter(trigger);
    const term = document.body.querySelector(".homepage-grade-badge-tooltip-term");
    expect(term).not.toBeNull();
    // Translation key is echoed by the mock t() with the placeholder filled in.
    expect(term?.textContent ?? "").toContain("10");
  });

  it("omits the term line when years is not provided", () => {
    mockUseLearningMode.mockReturnValue({ enabled: true, available: true });
    const { container } = render(
      <HomepageGradeBadge ratings={{ overall: 3, pe10: 4 }} />,
    );
    const trigger = container.querySelector(".homepage-grade-badge") as HTMLElement;
    fireEvent.mouseEnter(trigger);
    expect(
      document.body.querySelector(".homepage-grade-badge-tooltip-term"),
    ).toBeNull();
  });
});
