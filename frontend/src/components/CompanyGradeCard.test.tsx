// @vitest-environment jsdom
import { describe, it, expect, afterEach, vi } from "vitest";
import { render, cleanup } from "@testing-library/react";
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
    const { container } = render(<CompanyGradeCard overall={4} />);
    expect(container.querySelector(".company-grade-card")).toBeNull();
  });

  it("renders the grade numeral when an overall is provided", () => {
    mockUseLearningMode.mockReturnValue({ enabled: true, available: true });
    const { container } = render(<CompanyGradeCard overall={4} />);
    const card = container.querySelector(".company-grade-card");
    expect(card).not.toBeNull();
    expect(card?.textContent).toContain("4");
  });

  it("renders an empty-state when overall is null", () => {
    mockUseLearningMode.mockReturnValue({ enabled: true, available: true });
    const { container } = render(<CompanyGradeCard overall={null} />);
    expect(container.querySelector(".company-grade-card")).not.toBeNull();
    expect(container.querySelector(".company-grade-card-empty")).not.toBeNull();
  });

  it("applies tier-specific class for color coding", () => {
    mockUseLearningMode.mockReturnValue({ enabled: true, available: true });
    const { container } = render(<CompanyGradeCard overall={5} />);
    expect(container.querySelector(".company-grade-card-tier-5")).not.toBeNull();
  });
});
