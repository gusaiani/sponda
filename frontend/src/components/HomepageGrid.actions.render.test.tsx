// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, cleanup } from "@testing-library/react";
import { CardActions } from "./HomepageGrid";

afterEach(cleanup);

vi.mock("../i18n", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    locale: "pt",
  }),
}));

/** Classify each direct child of the action row by its identifying class,
 *  so we can assert the left-to-right (DOM) order independent of markup. */
function actionOrder(): string[] {
  const row = document.querySelector(".homepage-grid-card-actions");
  if (!row) return [];
  return Array.from(row.children).map((child) => {
    if (child.classList.contains("homepage-grid-sponds-button")) return "sponds";
    if (child.classList.contains("homepage-grid-favorite-handle")) return "favorite";
    if (child.classList.contains("homepage-grid-share-wrapper")) return "share";
    if (child.classList.contains("homepage-grid-drag-handle")) return "drag";
    return "unknown";
  });
}

describe("CardActions icon order", () => {
  it("renders the Sponds balloon first (leftmost), then favorite, share, drag", () => {
    render(
      <CardActions
        favoriteState="outlined"
        itemType="ticker"
        itemId="PETR4"
        lists={[]}
        onFavoriteClick={() => {}}
        onOpenSponds={() => {}}
      />,
    );

    expect(actionOrder()).toEqual(["sponds", "favorite", "share", "drag"]);
  });
});
