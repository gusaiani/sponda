// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach, beforeAll } from "vitest";
import { render, cleanup } from "@testing-library/react";
import { ListCard } from "./ListCard";

beforeAll(() => {
  class ResizeObserverStub {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  // @ts-expect-error — jsdom lacks ResizeObserver
  globalThis.ResizeObserver = ResizeObserverStub;
});

afterEach(cleanup);

vi.mock("../hooks/useCompareData", () => ({
  useCompareData: (tickers: string[]) =>
    tickers.map((ticker) => ({
      ticker,
      data: null,
      isLoading: true,
      error: null,
    })),
}));

vi.mock("../i18n", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    locale: "pt",
  }),
}));

describe("ListCard ticker cell", () => {
  it("renders a company logo image for each visible ticker", () => {
    render(<ListCard listId={1} name="Renner e setor" tickers={["LREN3", "AMAR3"]} years={10} />);

    const logos = document.querySelectorAll("img.list-card-logo");
    expect(logos.length).toBe(2);
    expect((logos[0] as HTMLImageElement).src).toContain("/api/logos/LREN3.png");
    expect((logos[1] as HTMLImageElement).src).toContain("/api/logos/AMAR3.png");
  });

  it("keeps the ticker text next to the logo", () => {
    render(<ListCard listId={1} name="Renner" tickers={["LREN3"]} years={10} />);

    const tickerCell = document.querySelector(".list-card-ticker");
    expect(tickerCell).not.toBeNull();
    expect(tickerCell!.textContent).toContain("LREN3");
    expect(tickerCell!.querySelector("img.list-card-logo")).not.toBeNull();
  });
});
