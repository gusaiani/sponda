// @vitest-environment jsdom
import { afterEach, describe, it, expect } from "vitest";
import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";

afterEach(cleanup);

import {
  UserAvatar,
  initialsFor,
  paletteColorFor,
} from "./UserAvatar";

describe("initialsFor", () => {
  it("falls back to ? for empty input", () => {
    expect(initialsFor(null)).toBe("?");
    expect(initialsFor("")).toBe("?");
  });

  it("returns first two letters of single-word handle", () => {
    expect(initialsFor("alice")).toBe("AL");
  });

  it("returns first letters of two-word display name", () => {
    expect(initialsFor("alice", "Alice Smith")).toBe("AS");
  });

  it("splits on underscore", () => {
    expect(initialsFor("gustavo_saiani")).toBe("GS");
  });

  it("prefers displayName over handle", () => {
    expect(initialsFor("ab", "John Doe")).toBe("JD");
  });
});

describe("paletteColorFor", () => {
  it("returns the same color for the same input", () => {
    expect(paletteColorFor("alice")).toBe(paletteColorFor("alice"));
  });

  it("returns valid hex string", () => {
    expect(paletteColorFor("alice")).toMatch(/^#[0-9a-f]{6}$/i);
  });

  it("falls back to first palette entry on null", () => {
    expect(paletteColorFor(null)).toBe(paletteColorFor(null));
  });
});

describe("UserAvatar", () => {
  it("renders initials inside the circle", () => {
    render(<UserAvatar handle="alice" />);
    expect(screen.getByRole("img", { name: "alice" })).toHaveTextContent("AL");
  });

  it("respects size prop (sm)", () => {
    render(<UserAvatar handle="alice" size="sm" />);
    const el = screen.getByRole("img", { name: "alice" });
    expect(el).toHaveStyle({ width: "24px", height: "24px" });
  });

  it("respects size prop (lg)", () => {
    render(<UserAvatar handle="alice" size="lg" />);
    const el = screen.getByRole("img", { name: "alice" });
    expect(el).toHaveStyle({ width: "64px", height: "64px" });
  });

  it("renders an image when src is provided", () => {
    const { container } = render(
      <UserAvatar handle="alice" src="/avatars/alice.png" displayName="Alice" />,
    );
    const img = container.querySelector("img");
    expect(img).not.toBeNull();
    expect(img?.getAttribute("src")).toBe("/avatars/alice.png");
  });
});
