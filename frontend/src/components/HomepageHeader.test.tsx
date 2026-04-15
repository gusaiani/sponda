// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, cleanup, fireEvent } from "@testing-library/react";
import { HomepageHeader, shouldShowEmptyFavoritesCta } from "./HomepageHeader";

afterEach(cleanup);

vi.mock("../i18n", () => ({
  useTranslation: () => ({
    t: (key: string) => {
      if (key === "homepage.your_favorites") return "Suas Favoritas";
      if (key === "homepage.favorites_empty_cta") return "Favorite empresas e crie listas para vê-las aqui";
      return key;
    },
    locale: "pt",
  }),
}));

describe("shouldShowEmptyFavoritesCta", () => {
  it("returns true when not authenticated (regardless of counts)", () => {
    expect(
      shouldShowEmptyFavoritesCta({ isAuthenticated: false, favoriteCount: 0, listCount: 0 }),
    ).toBe(true);
    expect(
      shouldShowEmptyFavoritesCta({ isAuthenticated: false, favoriteCount: 5, listCount: 2 }),
    ).toBe(true);
  });

  it("returns true when authenticated but has no favorites and no saved lists", () => {
    expect(
      shouldShowEmptyFavoritesCta({ isAuthenticated: true, favoriteCount: 0, listCount: 0 }),
    ).toBe(true);
  });

  it("returns false when authenticated user has at least one favorite", () => {
    expect(
      shouldShowEmptyFavoritesCta({ isAuthenticated: true, favoriteCount: 1, listCount: 0 }),
    ).toBe(false);
  });

  it("returns false when authenticated user has at least one saved list", () => {
    expect(
      shouldShowEmptyFavoritesCta({ isAuthenticated: true, favoriteCount: 0, listCount: 1 }),
    ).toBe(false);
  });
});

describe("HomepageHeader", () => {
  const noop = () => {};

  it("renders 'Suas Favoritas' when the user has favorites", () => {
    const { container } = render(
      <HomepageHeader
        isAuthenticated={true}
        favoriteCount={3}
        listCount={0}
        years={10}
        maxYears={16}
        onYearsChange={noop}
      />,
    );
    const name = container.querySelector(".homepage-header-name");
    expect(name).not.toBeNull();
    expect(name!.textContent).toBe("Suas Favoritas");
  });

  it("renders the empty-state CTA when unauthenticated", () => {
    const { container } = render(
      <HomepageHeader
        isAuthenticated={false}
        favoriteCount={0}
        listCount={0}
        years={10}
        maxYears={16}
        onYearsChange={noop}
      />,
    );
    const name = container.querySelector(".homepage-header-name");
    expect(name!.textContent).toBe("Favorite empresas e crie listas para vê-las aqui");
  });

  it("renders the empty-state CTA when authenticated but no favorites and no lists", () => {
    const { container } = render(
      <HomepageHeader
        isAuthenticated={true}
        favoriteCount={0}
        listCount={0}
        years={10}
        maxYears={16}
        onYearsChange={noop}
      />,
    );
    const name = container.querySelector(".homepage-header-name");
    expect(name!.textContent).toBe("Favorite empresas e crie listas para vê-las aqui");
  });

  it("renders a circular Sponda favicon to the left of the headline", () => {
    const { container } = render(
      <HomepageHeader
        isAuthenticated={true}
        favoriteCount={2}
        listCount={0}
        years={10}
        maxYears={16}
        onYearsChange={noop}
      />,
    );
    const logo = container.querySelector(".homepage-header-logo");
    expect(logo).not.toBeNull();
    const circle = logo!.querySelector("circle");
    expect(circle).not.toBeNull();
    expect(circle!.getAttribute("cx")).toBe("16");
    expect(circle!.getAttribute("cy")).toBe("16");
    expect(circle!.getAttribute("r")).toBe("16");
    const text = logo!.querySelector("text");
    expect(text).not.toBeNull();
    expect(text!.textContent).toBe("S");
  });

  it("renders a YearsSlider that calls onYearsChange when moved", () => {
    const handleChange = vi.fn();
    const { container } = render(
      <HomepageHeader
        isAuthenticated={true}
        favoriteCount={2}
        listCount={0}
        years={10}
        maxYears={16}
        onYearsChange={handleChange}
      />,
    );
    const slider = container.querySelector<HTMLInputElement>(".years-slider-input");
    expect(slider).not.toBeNull();
    expect(slider!.min).toBe("1");
    expect(slider!.max).toBe("16");
    expect(slider!.value).toBe("10");

    fireEvent.change(slider!, { target: { value: "5" } });
    expect(handleChange).toHaveBeenCalledWith(5);
  });

  it("hides the slider when maxYears is 1 or less", () => {
    const { container } = render(
      <HomepageHeader
        isAuthenticated={true}
        favoriteCount={1}
        listCount={0}
        years={1}
        maxYears={1}
        onYearsChange={noop}
      />,
    );
    expect(container.querySelector(".years-slider-input")).toBeNull();
  });
});
