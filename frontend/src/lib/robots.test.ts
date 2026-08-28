import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const robots = readFileSync(join(__dirname, "../../public/robots.txt"), "utf-8");
const directives = robots.split("\n").map((line) => line.trim());

describe("robots.txt", () => {
  it("keeps the API closed to crawlers", () => {
    expect(directives).toContain("Disallow: /api/");
  });

  it("re-opens company logos, which every indexable page embeds", () => {
    // `Disallow: /api/` also covered `/api/logos/*.png`, so every crawler
    // saw the logo on every company page as a blocked resource.
    expect(directives).toContain("Allow: /api/logos/");
  });
});
