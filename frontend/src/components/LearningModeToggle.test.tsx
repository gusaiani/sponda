// @vitest-environment jsdom
import { describe, it, expect, afterEach, vi } from "vitest";
import { render, cleanup, fireEvent } from "@testing-library/react";
import { LearningModeToggle } from "./LearningModeToggle";

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

describe("LearningModeToggle", () => {
  it("renders nothing when learning mode is not available", () => {
    mockUseLearningMode.mockReturnValue({
      enabled: false,
      available: false,
      setEnabled: vi.fn(),
    });
    const { container } = render(<LearningModeToggle />);
    expect(container.querySelector(".learning-mode-toggle")).toBeNull();
  });

  it("renders an off pill when available and disabled", () => {
    mockUseLearningMode.mockReturnValue({
      enabled: false,
      available: true,
      setEnabled: vi.fn(),
    });
    const { container } = render(<LearningModeToggle />);
    const button = container.querySelector(".learning-mode-toggle");
    expect(button).not.toBeNull();
    expect(button?.classList.contains("learning-mode-toggle--on")).toBe(false);
    expect(button?.getAttribute("aria-pressed")).toBe("false");
  });

  it("renders an on pill when available and enabled", () => {
    mockUseLearningMode.mockReturnValue({
      enabled: true,
      available: true,
      setEnabled: vi.fn(),
    });
    const { container } = render(<LearningModeToggle />);
    const button = container.querySelector(".learning-mode-toggle");
    expect(button?.classList.contains("learning-mode-toggle--on")).toBe(true);
    expect(button?.getAttribute("aria-pressed")).toBe("true");
  });

  it("calls setEnabled with the toggled value on click", () => {
    const setEnabled = vi.fn();
    mockUseLearningMode.mockReturnValue({
      enabled: false,
      available: true,
      setEnabled,
    });
    const { container } = render(<LearningModeToggle />);
    const button = container.querySelector(".learning-mode-toggle") as HTMLButtonElement;
    fireEvent.click(button);
    expect(setEnabled).toHaveBeenCalledWith(true);
  });
});
