import { describe, it, expect } from "vitest";
import { getGridItemClassNames } from "./HomepageGrid";

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
