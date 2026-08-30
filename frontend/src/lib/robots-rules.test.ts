import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import path from "node:path";
import { isPathAllowedByRobots } from "./robots-rules";

const ROBOTS_TXT = readFileSync(path.join(process.cwd(), "public", "robots.txt"), "utf8");

describe("isPathAllowedByRobots", () => {
  it("applies a wildcard rule the way Google and X do", () => {
    const rules = "User-agent: *\nDisallow: /*/login\n";
    expect(isPathAllowedByRobots(rules, "/pt/login")).toBe(false);
    expect(isPathAllowedByRobots(rules, "/pt/login-help")).toBe(false);
    expect(isPathAllowedByRobots(rules, "/pt/VULC3")).toBe(true);
  });

  it("lets the longest matching rule win, so Allow: / does not override a Disallow", () => {
    const rules = "User-agent: *\nAllow: /\nDisallow: /api/\n";
    expect(isPathAllowedByRobots(rules, "/api/quote/X/")).toBe(false);
    expect(isPathAllowedByRobots(rules, "/pt")).toBe(true);
  });
});

describe("public/robots.txt", () => {
  it("lets crawlers fetch every Open Graph image", () => {
    for (const imagePath of [
      "/og/site/en.jpg",
      "/og/site/pt.jpg",
      "/og/pt/VULC3.png",
      "/images/sponda-og-en-v2.jpg",
      "/images/sponda-og-v2.jpg",
    ]) {
      expect(isPathAllowedByRobots(ROBOTS_TXT, imagePath), imagePath).toBe(true);
    }
  });

  it("still keeps crawlers out of the social pages", () => {
    for (const socialPath of ["/pt/user/gustavo", "/en/spond/123", "/user/gustavo", "/spond/123"]) {
      expect(isPathAllowedByRobots(ROBOTS_TXT, socialPath), socialPath).toBe(false);
    }
  });

  it("does not hide a company whose ticker starts with USER or SPOND", () => {
    expect(isPathAllowedByRobots(ROBOTS_TXT, "/en/USER")).toBe(true);
    expect(isPathAllowedByRobots(ROBOTS_TXT, "/og/en/USER.png")).toBe(true);
  });
});
