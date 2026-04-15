import { describe, it, expect } from "vitest";
import { getAddFavoriteCardPosition } from "./AddFavoriteCard";

describe("getAddFavoriteCardPosition", () => {
  it("places the card first when the user is not authenticated", () => {
    expect(getAddFavoriteCardPosition({ isAuthenticated: false, favoriteCount: 0 })).toBe(
      "first",
    );
  });

  it("places the card first when an authenticated user has zero favorites", () => {
    expect(getAddFavoriteCardPosition({ isAuthenticated: true, favoriteCount: 0 })).toBe(
      "first",
    );
  });

  it("places the card last when the authenticated user has at least one favorite", () => {
    expect(getAddFavoriteCardPosition({ isAuthenticated: true, favoriteCount: 1 })).toBe(
      "last",
    );
    expect(getAddFavoriteCardPosition({ isAuthenticated: true, favoriteCount: 10 })).toBe(
      "last",
    );
  });
});
