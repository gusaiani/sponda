import { describe, it, expect } from "vitest";
import { getGridItemClassNames, getHomepageTickers, computeHomepageMaxYears } from "./HomepageGrid";

describe("getGridItemClassNames", () => {
  it("always includes the base class", () => {
    const result = getGridItemClassNames(false, false, false);
    expect(result).toBe("homepage-grid-item");
  });

  it("adds span-2 class for list items", () => {
    const result = getGridItemClassNames(true, false, false);
    expect(result).toContain("homepage-grid-item--span-2");
    expect(result).toContain("homepage-grid-item");
  });

  it("adds dragging class when item is being dragged", () => {
    const result = getGridItemClassNames(false, true, false);
    expect(result).toContain("homepage-grid-item--dragging");
    expect(result).not.toContain("homepage-grid-item--drag-over");
  });

  it("adds drag-over class when item is a drop target", () => {
    const result = getGridItemClassNames(false, false, true);
    expect(result).toContain("homepage-grid-item--drag-over");
    expect(result).not.toContain("homepage-grid-item--dragging");
  });

  it("does not add dragging and drag-over simultaneously in normal usage", () => {
    // An item being dragged should never also be a drop target
    const draggingItem = getGridItemClassNames(false, true, false);
    expect(draggingItem).toContain("homepage-grid-item--dragging");
    expect(draggingItem).not.toContain("homepage-grid-item--drag-over");
  });

  it("combines span-2 with drag states", () => {
    const result = getGridItemClassNames(true, true, false);
    expect(result).toContain("homepage-grid-item--span-2");
    expect(result).toContain("homepage-grid-item--dragging");
  });

  it("produces space-separated class string with no extra spaces", () => {
    const result = getGridItemClassNames(false, false, false);
    expect(result).not.toMatch(/  /); // no double spaces
    expect(result).not.toMatch(/^ /); // no leading space
    expect(result).not.toMatch(/ $/); // no trailing space
  });

  it("produces all four classes when every flag is true", () => {
    const result = getGridItemClassNames(true, true, true);
    expect(result).toBe(
      "homepage-grid-item homepage-grid-item--span-2 homepage-grid-item--dragging homepage-grid-item--drag-over",
    );
  });
});

describe("getHomepageTickers", () => {
  const fifteenFavorites = Array.from({ length: 15 }, (_, i) => `FAV${i}`);
  const defaults = Array.from({ length: 10 }, (_, i) => `DFT${i}`);

  it("caps unverified authenticated users at 8 favorites", () => {
    const result = getHomepageTickers({
      isAuthenticated: true,
      isVerified: false,
      favoriteTickers: fifteenFavorites,
      defaultTickers: defaults,
      showPlaceholder: false,
    });
    expect(result).toHaveLength(8);
    expect(result[0]).toBe("FAV0");
  });

  it("shows all favorites for verified authenticated users", () => {
    const result = getHomepageTickers({
      isAuthenticated: true,
      isVerified: true,
      favoriteTickers: fifteenFavorites,
      defaultTickers: defaults,
      showPlaceholder: false,
    });
    expect(result).toHaveLength(15);
    expect(result).toEqual(fifteenFavorites);
  });

  it("does not slice when verified user has fewer than 8 favorites", () => {
    const favorites = ["A", "B", "C"];
    const result = getHomepageTickers({
      isAuthenticated: true,
      isVerified: true,
      favoriteTickers: favorites,
      defaultTickers: defaults,
      showPlaceholder: false,
    });
    expect(result).toEqual(favorites);
  });

  it("shows 8 default tickers for unauthenticated users without placeholder", () => {
    const result = getHomepageTickers({
      isAuthenticated: false,
      isVerified: false,
      favoriteTickers: [],
      defaultTickers: defaults,
      showPlaceholder: false,
    });
    expect(result).toHaveLength(8);
  });

  it("shows 7 default tickers when the add-favorite placeholder is visible", () => {
    const result = getHomepageTickers({
      isAuthenticated: true,
      isVerified: true,
      favoriteTickers: [],
      defaultTickers: defaults,
      showPlaceholder: true,
    });
    expect(result).toHaveLength(7);
  });
});

describe("computeHomepageMaxYears", () => {
  const DEFAULT = 10;

  it("returns the max maxYearsAvailable across loaded companies", () => {
    const result = computeHomepageMaxYears(
      [
        { maxYearsAvailable: 8 },
        { maxYearsAvailable: 16 },
        { maxYearsAvailable: 12 },
      ],
      DEFAULT,
    );
    expect(result).toBe(16);
  });

  it("ignores nulls from companies still loading", () => {
    const result = computeHomepageMaxYears(
      [{ maxYearsAvailable: null }, { maxYearsAvailable: 15 }],
      DEFAULT,
    );
    expect(result).toBe(15);
  });

  it("falls back to the default when no data has loaded", () => {
    const result = computeHomepageMaxYears([], DEFAULT);
    expect(result).toBe(DEFAULT);
  });

  it("falls back to the default when every entry is still loading", () => {
    const result = computeHomepageMaxYears(
      [{ maxYearsAvailable: null }, { maxYearsAvailable: null }],
      DEFAULT,
    );
    expect(result).toBe(DEFAULT);
  });

  it("returns the single company value when only one company is loaded", () => {
    const result = computeHomepageMaxYears(
      [{ maxYearsAvailable: 5 }],
      DEFAULT,
    );
    expect(result).toBe(5);
  });
});
