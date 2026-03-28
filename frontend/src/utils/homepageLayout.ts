export interface LayoutItem {
  type: "ticker" | "list";
  id: string;
}

/**
 * Build a default layout: tickers with lists interspersed every 4 tickers.
 */
export function buildDefaultLayout(
  tickers: string[],
  lists: { id: number }[],
): LayoutItem[] {
  const layout: LayoutItem[] = [];
  const listQueue = [...lists];
  const tickersPerGroup = 4;

  for (let i = 0; i < tickers.length; i++) {
    layout.push({ type: "ticker", id: tickers[i] });
    if ((i + 1) % tickersPerGroup === 0 && listQueue.length > 0) {
      const list = listQueue.shift()!;
      layout.push({ type: "list", id: String(list.id) });
    }
  }

  // Append remaining lists
  for (const list of listQueue) {
    layout.push({ type: "list", id: String(list.id) });
  }

  return layout;
}

/**
 * Merge a saved layout with current data, removing stale items
 * and appending new ones.
 */
export function mergeLayoutWithData(
  saved: LayoutItem[],
  currentTickers: string[],
  currentLists: { id: number }[],
): LayoutItem[] {
  const tickerSet = new Set(currentTickers);
  const listSet = new Set(currentLists.map((l) => String(l.id)));

  // Keep saved items that still exist
  const result = saved.filter((item) => {
    if (item.type === "ticker") return tickerSet.has(item.id);
    return listSet.has(item.id);
  });

  // Track what's already in the layout
  const present = new Set(result.map((item) => `${item.type}:${item.id}`));

  // Append new items not in saved layout
  for (const ticker of currentTickers) {
    if (!present.has(`ticker:${ticker}`)) {
      result.push({ type: "ticker", id: ticker });
    }
  }
  for (const list of currentLists) {
    const id = String(list.id);
    if (!present.has(`list:${id}`)) {
      result.push({ type: "list", id });
    }
  }

  return result;
}

/**
 * Move an item from one index to another, returning a new array.
 */
export function moveItem(layout: LayoutItem[], from: number, to: number): LayoutItem[] {
  if (from === to) return layout;
  const result = [...layout];
  const [moved] = result.splice(from, 1);
  result.splice(to, 0, moved);
  return result;
}
