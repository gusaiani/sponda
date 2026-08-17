// @vitest-environment jsdom
import { describe, it, expect, vi, beforeAll, afterEach } from "vitest";
import { render, cleanup, fireEvent } from "@testing-library/react";
import { CompanySearchInput } from "./CompanySearchInput";
import type { TickerItem } from "../hooks/useTickerSearch";

beforeAll(() => {
  // jsdom does not implement scrollIntoView
  Element.prototype.scrollIntoView = vi.fn();
});

afterEach(() => {
  cleanup();
  mockResults = [];
});

let mockResults: TickerItem[] = [];

vi.mock("../hooks/useTickerSearch", () => ({
  useTickerSearch: () => ({
    results: mockResults,
    isSearching: false,
  }),
}));

vi.mock("../i18n", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    locale: "pt",
  }),
}));

function setMockResults(items: TickerItem[]) {
  mockResults = items;
}

function makeItem(symbol: string, name: string): TickerItem {
  return { symbol, name, sector: "", type: "stock", logo: "" };
}

function renderInput(onAdd = vi.fn()) {
  const utils = render(
    <CompanySearchInput onAdd={onAdd} excludeTickers={[]} />,
  );
  const input = utils.container.querySelector(
    ".compare-add-input",
  ) as HTMLInputElement;
  return { ...utils, input, onAdd };
}

function typeAndOpen(input: HTMLInputElement, value: string) {
  fireEvent.focus(input);
  fireEvent.change(input, { target: { value } });
}

describe("CompanySearchInput Enter key behavior", () => {
  it("adds the highlighted ticker when Enter is pressed", () => {
    setMockResults([
      makeItem("WDAY", "Workday, Inc."),
      makeItem("WMT", "Walmart Inc."),
    ]);
    const { input, onAdd } = renderInput();

    typeAndOpen(input, "w");
    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(onAdd).toHaveBeenCalledWith("WMT");
  });

  it("adds the first dropdown ticker when Enter is pressed with no highlight", () => {
    setMockResults([
      makeItem("WDAY", "Workday, Inc."),
      makeItem("WMT", "Walmart Inc."),
    ]);
    const { input, onAdd } = renderInput();

    typeAndOpen(input, "workday");
    fireEvent.keyDown(input, { key: "Enter" });

    expect(onAdd).toHaveBeenCalledWith("WDAY");
  });

  it("falls back to raw input when there are no results", () => {
    setMockResults([]);
    const { input, onAdd } = renderInput();

    typeAndOpen(input, "xyz");
    fireEvent.keyDown(input, { key: "Enter" });

    expect(onAdd).toHaveBeenCalledWith("XYZ");
  });
});


describe("CompanySearchInput highlight reset", () => {
  // Characterisation test for the highlight-reset behaviour, written before
  // moving that reset out of an effect. It has to pass identically before and
  // after: stale highlights are how a user ends up adding the wrong company.
  // The dropdown is rendered through createPortal, so it lives on
  // document.body rather than inside the component's container.
  function activeSymbols(): string[] {
    return Array.from(document.querySelectorAll(".search-dropdown-item--active"))
      .map((element) => element.textContent || "");
  }

  it("highlights the arrowed-to item", () => {
    setMockResults([makeItem("WDAY", "Workday, Inc."), makeItem("WMT", "Walmart Inc.")]);
    const { input } = renderInput();

    typeAndOpen(input, "w");
    fireEvent.keyDown(input, { key: "ArrowDown" });

    expect(activeSymbols()).toHaveLength(1);
    expect(activeSymbols()[0]).toContain("WDAY");
  });

  it("drops the highlight when the result list changes underneath it", () => {
    setMockResults([makeItem("WDAY", "Workday, Inc."), makeItem("WMT", "Walmart Inc.")]);
    const { input } = renderInput();

    typeAndOpen(input, "w");
    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "ArrowDown" });
    expect(activeSymbols()[0]).toContain("WMT");

    // Deliberately the SAME length, so index 1 still exists in the new list.
    // A shorter list would hide the stale highlight by falling out of range
    // and the test would pass even with the reset deleted.
    setMockResults([makeItem("PETR4", "Petrobras"), makeItem("PETR3", "Petrobras ON")]);
    fireEvent.change(input, { target: { value: "pe" } });

    expect(activeSymbols()).toHaveLength(0);
  });

  it("adds the typed text, not a stale highlight, after the list changes", () => {
    setMockResults([makeItem("WDAY", "Workday, Inc."), makeItem("WMT", "Walmart Inc.")]);
    const { input, onAdd } = renderInput();

    typeAndOpen(input, "w");
    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "ArrowDown" });

    // Same length again, so a surviving index 1 would resolve to PETR3.
    setMockResults([makeItem("PETR4", "Petrobras"), makeItem("PETR3", "Petrobras ON")]);
    fireEvent.change(input, { target: { value: "pe" } });
    expect(activeSymbols()).toHaveLength(0);

    // No highlight, so Enter takes the first result rather than the stale index.
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onAdd).toHaveBeenCalledWith("PETR4");
  });
});
