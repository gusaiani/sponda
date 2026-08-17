// @vitest-environment jsdom
import { describe, it, expect, vi, beforeAll, afterEach } from "vitest";
import { render, cleanup, fireEvent } from "@testing-library/react";
import { SearchBar } from "./SearchBar";
import type { TickerItem } from "../hooks/useTickerSearch";

/**
 * SearchBar had no tests. These were written before moving its
 * highlight reset out of an effect, so they have to pass identically
 * before and after: a stale highlight means Enter searches the wrong
 * company.
 */

beforeAll(() => {
  // jsdom does not implement scrollIntoView, which the dropdown calls when
  // the highlight moves.
  Element.prototype.scrollIntoView = vi.fn();
});

let mockResults: TickerItem[] = [];

vi.mock("../hooks/useTickerSearch", () => ({
  useTickerSearch: () => ({ results: mockResults, isSearching: false }),
}));

vi.mock("../i18n", () => ({
  useTranslation: () => ({ t: (key: string) => key, locale: "pt" }),
}));

afterEach(() => {
  cleanup();
  mockResults = [];
});

function makeItem(symbol: string, name: string): TickerItem {
  return { symbol, name, sector: "", type: "stock", logo: "" };
}

function renderSearchBar() {
  const onSearch = vi.fn();
  const utils = render(<SearchBar onSearch={onSearch} isLoading={false} />);
  const input = utils.container.querySelector(".search-input") as HTMLInputElement;
  return { ...utils, input, onSearch };
}

function openWith(input: HTMLInputElement, value: string) {
  fireEvent.focus(input);
  fireEvent.change(input, { target: { value } });
}

function activeItems(): string[] {
  return Array.from(document.querySelectorAll(".search-dropdown-item--active"))
    .map((element) => element.textContent || "");
}

describe("SearchBar keyboard selection", () => {
  it("highlights the arrowed-to result", () => {
    mockResults = [makeItem("WDAY", "Workday"), makeItem("WMT", "Walmart")];
    const { input } = renderSearchBar();

    openWith(input, "w");
    fireEvent.keyDown(input, { key: "ArrowDown" });

    expect(activeItems()).toHaveLength(1);
    expect(activeItems()[0]).toContain("WDAY");
  });

  it("searches the highlighted result on submit", () => {
    mockResults = [makeItem("WDAY", "Workday"), makeItem("WMT", "Walmart")];
    const { input, onSearch, container } = renderSearchBar();

    openWith(input, "w");
    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.submit(container.querySelector("form") as HTMLFormElement);

    expect(onSearch).toHaveBeenCalledWith("WMT");
  });

  it("searches the raw input when nothing is highlighted", () => {
    mockResults = [];
    const { input, onSearch, container } = renderSearchBar();

    openWith(input, "petr4");
    fireEvent.submit(container.querySelector("form") as HTMLFormElement);

    expect(onSearch).toHaveBeenCalledWith("PETR4");
  });

  it("drops the highlight when the results change underneath it", () => {
    mockResults = [makeItem("WDAY", "Workday"), makeItem("WMT", "Walmart")];
    const { input } = renderSearchBar();

    openWith(input, "w");
    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "ArrowDown" });
    expect(activeItems()[0]).toContain("WMT");

    // Same length on purpose: a shorter list would drop the highlight by
    // falling out of range, and the test would pass even with no reset.
    mockResults = [makeItem("PETR4", "Petrobras"), makeItem("PETR3", "Petrobras ON")];
    fireEvent.change(input, { target: { value: "pe" } });

    expect(activeItems()).toHaveLength(0);
  });

  it("submits the typed text rather than a stale highlight", () => {
    mockResults = [makeItem("WDAY", "Workday"), makeItem("WMT", "Walmart")];
    const { input, onSearch, container } = renderSearchBar();

    openWith(input, "w");
    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "ArrowDown" });

    mockResults = [makeItem("PETR4", "Petrobras"), makeItem("PETR3", "Petrobras ON")];
    fireEvent.change(input, { target: { value: "petr4" } });
    fireEvent.submit(container.querySelector("form") as HTMLFormElement);

    expect(onSearch).toHaveBeenCalledWith("PETR4");
  });
});
