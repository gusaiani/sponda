import { describe, it, expect } from "vitest";
import { shouldShowAddFavoriteCard } from "./AddFavoriteCard";

describe("shouldShowAddFavoriteCard", () => {
  it("returns true when not authenticated (shows as 8th card)", () => {
    expect(shouldShowAddFavoriteCard(false, 0)).toBe(true);
  });

  it("returns true when user has 1 to 3 favorites", () => {
    expect(shouldShowAddFavoriteCard(true, 1)).toBe(true);
    expect(shouldShowAddFavoriteCard(true, 2)).toBe(true);
    expect(shouldShowAddFavoriteCard(true, 3)).toBe(true);
  });

  it("returns false when user has 4 or more favorites", () => {
    expect(shouldShowAddFavoriteCard(true, 4)).toBe(false);
    expect(shouldShowAddFavoriteCard(true, 8)).toBe(false);
  });

  it("returns false when authenticated with no favorites (shows default 8)", () => {
    expect(shouldShowAddFavoriteCard(true, 0)).toBe(false);
  });
});
