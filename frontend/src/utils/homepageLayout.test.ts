import { describe, it, expect } from "vitest";
import {
  buildDefaultLayout,
  mergeLayoutWithData,
  moveItem,
  type LayoutItem,
} from "./homepageLayout";

const DEFAULT_TICKERS = ["PETR4", "VALE3", "ITUB4", "WEGE3", "ABEV3", "BBAS3", "RENT3", "SUZB3"];

describe("buildDefaultLayout", () => {
  it("creates ticker items for each default ticker", () => {
    const layout = buildDefaultLayout(DEFAULT_TICKERS, []);
    expect(layout).toHaveLength(8);
    expect(layout[0]).toEqual({ type: "ticker", id: "PETR4" });
    expect(layout[7]).toEqual({ type: "ticker", id: "SUZB3" });
  });

  it("includes list items interspersed after every 4 tickers", () => {
    const lists = [{ id: 1 }, { id: 2 }];
    const layout = buildDefaultLayout(DEFAULT_TICKERS, lists);
    // 4 tickers, then list 1, then 4 tickers, then list 2
    expect(layout[4]).toEqual({ type: "list", id: "1" });
    expect(layout[9]).toEqual({ type: "list", id: "2" });
    expect(layout).toHaveLength(10);
  });

  it("handles no lists", () => {
    const layout = buildDefaultLayout(DEFAULT_TICKERS, []);
    expect(layout.every((item) => item.type === "ticker")).toBe(true);
  });

  it("handles no tickers", () => {
    const lists = [{ id: 1 }];
    const layout = buildDefaultLayout([], lists);
    expect(layout).toEqual([{ type: "list", id: "1" }]);
  });
});

describe("mergeLayoutWithData", () => {
  it("preserves saved layout order", () => {
    const saved: LayoutItem[] = [
      { type: "ticker", id: "VALE3" },
      { type: "list", id: "1" },
      { type: "ticker", id: "PETR4" },
    ];
    const result = mergeLayoutWithData(saved, ["PETR4", "VALE3"], [{ id: 1 }]);
    expect(result).toEqual(saved);
  });

  it("removes items no longer present in data", () => {
    const saved: LayoutItem[] = [
      { type: "ticker", id: "PETR4" },
      { type: "ticker", id: "REMOVED3" },
      { type: "list", id: "99" },
    ];
    const result = mergeLayoutWithData(saved, ["PETR4"], []);
    expect(result).toEqual([{ type: "ticker", id: "PETR4" }]);
  });

  it("appends new items not in saved layout", () => {
    const saved: LayoutItem[] = [
      { type: "ticker", id: "PETR4" },
    ];
    const result = mergeLayoutWithData(saved, ["PETR4", "VALE3"], [{ id: 5 }]);
    expect(result).toHaveLength(3);
    expect(result[0]).toEqual({ type: "ticker", id: "PETR4" });
    // New items appended
    expect(result.find((i) => i.id === "VALE3")).toBeTruthy();
    expect(result.find((i) => i.id === "5")).toBeTruthy();
  });
});

describe("moveItem", () => {
  const layout: LayoutItem[] = [
    { type: "ticker", id: "A" },
    { type: "ticker", id: "B" },
    { type: "list", id: "1" },
    { type: "ticker", id: "C" },
  ];

  it("moves an item forward", () => {
    const result = moveItem(layout, 0, 2);
    expect(result.map((i) => i.id)).toEqual(["B", "1", "A", "C"]);
  });

  it("moves an item backward", () => {
    const result = moveItem(layout, 3, 0);
    expect(result.map((i) => i.id)).toEqual(["C", "A", "B", "1"]);
  });

  it("returns same layout when from equals to", () => {
    const result = moveItem(layout, 1, 1);
    expect(result).toEqual(layout);
  });

  it("handles moving to last position", () => {
    const result = moveItem(layout, 0, 3);
    expect(result.map((i) => i.id)).toEqual(["B", "1", "C", "A"]);
  });
});
