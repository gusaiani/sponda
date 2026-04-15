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

