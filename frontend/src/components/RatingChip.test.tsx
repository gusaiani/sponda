// @vitest-environment jsdom
import { describe, it, expect, afterEach, vi } from "vitest";
import { render, cleanup } from "@testing-library/react";
import { RatingChip } from "./RatingChip";

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

describe("RatingChip", () => {
  it("renders nothing when learning mode is disabled", () => {
    mockUseLearningMode.mockReturnValue({ enabled: false, available: true });
    const { container } = render(
      <RatingChip rating={4} indicator="pe10" />,
    );
    expect(container.querySelector(".rating-chip")).toBeNull();
  });

  it("renders nothing when rating is null", () => {
    mockUseLearningMode.mockReturnValue({ enabled: true, available: true });
    const { container } = render(
      <RatingChip rating={null} indicator="pe10" />,
    );
    expect(container.querySelector(".rating-chip")).toBeNull();
  });

  it("renders the tier numeral when enabled with a valid rating", () => {
    mockUseLearningMode.mockReturnValue({ enabled: true, available: true });
    const { container } = render(
      <RatingChip rating={4} indicator="pe10" />,
    );
    const chip = container.querySelector(".rating-chip");
    expect(chip).not.toBeNull();
    expect(chip?.textContent).toContain("4");
  });

  it("applies tier-specific class for color coding", () => {
    mockUseLearningMode.mockReturnValue({ enabled: true, available: true });
    const { container } = render(
      <RatingChip rating={5} indicator="pe10" />,
    );
    expect(container.querySelector(".rating-chip-tier-5")).not.toBeNull();
  });

  it("shows tier label and indicator name in aria-label", () => {
    mockUseLearningMode.mockReturnValue({ enabled: true, available: true });
    const { container } = render(
      <RatingChip rating={3} indicator="pe10" />,
    );
    const chip = container.querySelector(".rating-chip") as HTMLElement;
    expect(chip.getAttribute("aria-label")).toContain("learning.indicator.pe10.title");
    expect(chip.getAttribute("aria-label")).toContain("learning.tier.3");
  });
});
