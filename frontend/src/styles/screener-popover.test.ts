import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import path from "node:path";

/**
 * jsdom does not lay anything out, so the popover's anchoring is pinned by
 * reading the stylesheet. The "more filters" popover is absolutely
 * positioned at top: 100% of its containing block. When no ancestor is
 * positioned, that block is the viewport, so the popover lands one screen
 * height below the top of the page and the button looks dead. The header
 * must therefore be the containing block.
 */
const STYLES_DIRECTORY = path.dirname(new URL(import.meta.url).pathname);

function stylesheet(fileName: string): string {
  return readFileSync(path.join(STYLES_DIRECTORY, fileName), "utf8");
}

/** Body of the first top-level `selector { ... }` rule, whitespace collapsed. */
function ruleBody(css: string, selector: string): string {
  const escapedSelector = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const rule = new RegExp(`(^|\\n)${escapedSelector}\\s*\\{([^}]*)\\}`);
  const match = css.match(rule);
  return (match?.[2] ?? "").replace(/\s+/g, " ");
}

describe("screener more-filters popover anchoring", () => {
  const screenerCss = stylesheet("screener.css");

  it("positions the popover absolutely below its containing block", () => {
    const popover = ruleBody(screenerCss, ".screener-filter-popover");
    expect(popover).toContain("position: absolute");
    expect(popover).toContain("top: 100%");
  });

  it("makes the header the popover's containing block", () => {
    const header = ruleBody(screenerCss, ".screener-header");
    expect(header).toContain("position: relative");
  });
});
