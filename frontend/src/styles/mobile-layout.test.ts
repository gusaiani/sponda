import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import path from "node:path";

/**
 * jsdom does not lay anything out, so the phone-layout rules are pinned by
 * reading the stylesheets. Each assertion names one regression that was
 * visible on a real phone: the header wrapping to two rows, indicator labels
 * bleeding out of their card, the page scrolling sideways, and modals taller
 * than the visible viewport.
 */
const STYLES_DIRECTORY = path.dirname(new URL(import.meta.url).pathname);
const PHONE_MEDIA_QUERY = "@media (max-width: 639px)";
const DESKTOP_MEDIA_QUERY = "@media (min-width: 640px)";

function stylesheet(fileName: string): string {
  return readFileSync(path.join(STYLES_DIRECTORY, fileName), "utf8");
}

/** Bodies of every block for `mediaQuery`, joined, whitespace collapsed. */
function mediaBlocks(css: string, mediaQuery: string): string {
  const bodies: string[] = [];
  let searchFrom = 0;
  for (;;) {
    const start = css.indexOf(mediaQuery, searchFrom);
    if (start === -1) break;
    const openingBrace = css.indexOf("{", start);
    let depth = 0;
    let index = openingBrace;
    for (; index < css.length; index++) {
      if (css[index] === "{") depth++;
      if (css[index] === "}") depth--;
      if (depth === 0) break;
    }
    bodies.push(css.slice(openingBrace + 1, index));
    searchFrom = index;
  }
  return bodies.join("\n").replace(/\s+/g, " ");
}

/** True when some `selector { ... }` rule in `css` carries `declaration`. */
function declares(css: string, selector: string, declaration: string): boolean {
  const escapedSelector = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const rule = new RegExp(`${escapedSelector}[^{]*\\{([^}]*)\\}`, "g");
  for (const match of css.matchAll(rule)) {
    if (match[1].replace(/\s+/g, " ").includes(declaration)) return true;
  }
  return false;
}

describe("phone header fits one row", () => {
  it("hides the header MCP pill on phones", () => {
    const phone = mediaBlocks(stylesheet("mcp-announcement.css"), PHONE_MEDIA_QUERY);
    expect(declares(phone, ".app-header-mcp-link", "display: none")).toBe(true);
  });

  it("shows the left-nav MCP entry only on phones", () => {
    const desktop = mediaBlocks(stylesheet("left-nav.css"), DESKTOP_MEDIA_QUERY);
    expect(declares(desktop, ".left-nav-item--mobile-only", "display: none")).toBe(true);
  });
});

describe("nothing scrolls the page sideways", () => {
  it("clips horizontal overflow at the app container", () => {
    expect(declares(stylesheet("global.css"), ".app-container", "overflow-x: clip")).toBe(true);
  });

  it("stacks indicator cards one per row on phones", () => {
    const phone = mediaBlocks(stylesheet("card.css"), PHONE_MEDIA_QUERY);
    expect(declares(phone, ".metrics-row", "grid-template-columns: minmax(0, 1fr)")).toBe(true);
  });

  it("lets indicator labels wrap instead of bleeding past the card on phones", () => {
    const phone = mediaBlocks(stylesheet("card.css"), PHONE_MEDIA_QUERY);
    expect(declares(phone, ".pe10-label", "white-space: normal")).toBe(true);
  });
});

describe("modals fit the visible viewport", () => {
  it("bounds the MCP announcement by the dynamic viewport height", () => {
    const css = stylesheet("mcp-announcement.css");
    expect(declares(css, ".mcp-announcement-panel", "max-height: calc(100dvh - 32px)")).toBe(true);
  });

  it("keeps the MCP install tabs on one scrollable line", () => {
    const css = stylesheet("mcp-announcement.css");
    expect(declares(css, ".mcp-announcement-tabs", "overflow-x: auto")).toBe(true);
    expect(declares(css, ".mcp-announcement-tab", "white-space: nowrap")).toBe(true);
  });

  it("never lets the expanded chart exceed its overlay", () => {
    const css = stylesheet("card.css");
    expect(declares(css, ".chart-fullscreen-content", "max-width: min(1400px, 100%)")).toBe(true);
    expect(declares(css, ".chart-fullscreen-content", "max-height: 100%")).toBe(true);
    const phone = mediaBlocks(css, PHONE_MEDIA_QUERY);
    expect(declares(phone, ".chart-fullscreen-content", "width: 100%")).toBe(true);
    expect(declares(phone, ".chart-fullscreen-content", "height: 100%")).toBe(true);
  });
});
