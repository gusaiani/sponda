// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, cleanup } from "@testing-library/react";
import { ListHeader } from "./ListHeader";

afterEach(cleanup);

vi.mock("../i18n", () => ({
  useTranslation: () => ({
    t: (key: string, params?: Record<string, string | number>) =>
      params ? `${key}:${JSON.stringify(params)}` : key,
    pluralize: (count: number) => (count === 1 ? "year" : "years"),
    locale: "en",
  }),
}));

describe("ListHeader", () => {
  it("names the list, not the company the list was saved from", () => {
    const { container } = render(
      <ListHeader name="Poema" tickerCount={8} years={3} />,
    );
    const name = container.querySelector(".list-header-name");
    expect(name).not.toBeNull();
    expect(name!.textContent).toBe("Poema");
  });

  it("says how many companies the list holds and over what window", () => {
    const { container } = render(
      <ListHeader name="Poema" tickerCount={8} years={3} />,
    );
    const meta = container.querySelector(".list-header-meta");
    expect(meta!.textContent).toContain("8");
    expect(meta!.textContent).toContain("3");
  });

  it("carries no company logo, ticker, currency or rating", () => {
    const { container } = render(
      <ListHeader name="Poema" tickerCount={8} years={3} />,
    );
    expect(container.querySelector("img")).toBeNull();
    expect(container.textContent).not.toContain("DEXP4");
    expect(container.textContent).not.toContain("Currency");
  });
});
