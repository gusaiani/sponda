// @vitest-environment jsdom
import { describe, it, expect, vi, beforeAll, afterEach } from "vitest";
import { render, cleanup, fireEvent } from "@testing-library/react";
import { AddFavoriteCard } from "./AddFavoriteCard";
import type { TickerItem } from "../hooks/useTickerSearch";

/**
 * The keyboard highlight in this dropdown is reset from an effect. These
 * tests pin the behaviour before moving that into the render pass, because
 * the identical pattern in CompanySearchInput turned out to be keyed wrongly
 * and would add the wrong company.
 */

beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn();
});

let mockResults: TickerItem[] = [];

vi.mock("../hooks/useTickerSearch", () => ({
  useTickerSearch: () => ({ results: mockResults, isSearching: false }),
}));

vi.mock("../hooks/useFavorites", () => ({
  useFavorites: () => ({ favoriteTickers: [] }),
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

function renderCard() {
  const onSelectTicker = vi.fn();
  const utils = render(<AddFavoriteCard onSelectTicker={onSelectTicker} />);
  const input = utils.container.querySelector("input") as HTMLInputElement;
  return { ...utils, input, onSelectTicker };
}

function openWith(input: HTMLInputElement, value: string) {
  fireEvent.focus(input);
  fireEvent.change(input, { target: { value } });
}

// Portalled to document.body.
function activeItems(): string[] {
  return Array.from(document.querySelectorAll(".search-dropdown-item--active"))
    .map((element) => element.textContent || "");
}

describe("AddFavoriteCard keyboard selection", () => {
  it("highlights the arrowed-to result", () => {
    mockResults = [makeItem("WDAY", "Workday"), makeItem("WMT", "Walmart")];
    const { input } = renderCard();

    openWith(input, "w");
    fireEvent.keyDown(input, { key: "ArrowDown" });

    expect(activeItems()).toHaveLength(1);
    expect(activeItems()[0]).toContain("WDAY");
  });

  it("adds the highlighted result on Enter", () => {
    mockResults = [makeItem("WDAY", "Workday"), makeItem("WMT", "Walmart")];
    const { input, onSelectTicker } = renderCard();

    openWith(input, "w");
    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(onSelectTicker).toHaveBeenCalledWith("WMT");
  });

  it("drops the highlight when the results change underneath it", () => {
    mockResults = [makeItem("WDAY", "Workday"), makeItem("WMT", "Walmart")];
    const { input } = renderCard();

    openWith(input, "w");
    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "ArrowDown" });
    expect(activeItems()[0]).toContain("WMT");

    // Same length deliberately: with a shorter list the stale index falls out
    // of range and the highlight clears on its own, so the test would pass
    // even with no reset at all.
    mockResults = [makeItem("PETR4", "Petrobras"), makeItem("PETR3", "Petrobras ON")];
    fireEvent.change(input, { target: { value: "pe" } });

    expect(activeItems()).toHaveLength(0);
  });

  it("never adds a stale highlight after the list changes", () => {
    mockResults = [makeItem("WDAY", "Workday"), makeItem("WMT", "Walmart")];
    const { input, onSelectTicker } = renderCard();

    openWith(input, "w");
    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "ArrowDown" });

    mockResults = [makeItem("PETR4", "Petrobras"), makeItem("PETR3", "Petrobras ON")];
    fireEvent.change(input, { target: { value: "pe" } });
    fireEvent.keyDown(input, { key: "Enter" });

    // Unlike SearchBar, Enter here has no "take the first result" fallback:
    // with nothing highlighted it adds nothing. What matters is that it does
    // not add PETR3, the company that inherited the stale index.
    expect(onSelectTicker).not.toHaveBeenCalled();
  });
});
