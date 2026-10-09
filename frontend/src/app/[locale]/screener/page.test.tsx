// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach, beforeAll } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "@testing-library/jest-dom/vitest";

vi.mock("next/navigation", () => ({
  useParams: () => ({ locale: "pt" }),
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => "/pt/screener",
}));

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

vi.mock("../../../i18n", () => ({
  useTranslation: () => ({ t: (key: string) => key, locale: "pt" }),
}));

vi.mock("../../../hooks/useScreener", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../../hooks/useScreener")>();
  return {
    ...original,
    useScreener: () => ({ data: undefined, isLoading: false, isFetching: false }),
    useScreenerSectors: () => ({ data: [] }),
    useScreenerCountries: () => ({ data: [] }),
  };
});

vi.mock("../../../hooks/useAuth", () => ({
  useAuth: () => ({ isAuthenticated: false, isLoading: false }),
}));

vi.mock("../../../hooks/useSavedScreenerFilters", () => ({
  useSavedScreenerFilters: () => ({
    filters: [],
    isLoading: false,
    saveFilter: { mutate: vi.fn(), isPending: false },
    updateFilter: { mutate: vi.fn(), isPending: false },
    deleteFilter: { mutate: vi.fn(), isPending: false },
  }),
}));

vi.mock("../../../hooks/useSavedLists", () => ({
  useSavedLists: () => ({
    lists: [],
    isLoading: false,
    saveList: { mutate: vi.fn(), isPending: false },
  }),
}));

vi.mock("../../../components/AuthModal", () => ({
  AuthModal: () => null,
}));

vi.mock("../../../components/ScreenerFilterPresets", () => ({
  ScreenerFilterPresets: () => null,
  SaveFilterPresetModal: () => null,
}));

vi.mock("../../../components/RatingChip", () => ({
  RatingChip: () => null,
}));

import ScreenerPage from "./page";

function renderScreener() {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <ScreenerPage />
    </QueryClientProvider>,
  );
}

function moreFiltersButton(): HTMLElement {
  return screen.getByRole("button", { name: "screener.more_filters" });
}

beforeAll(() => {
  class ResizeObserverStub {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  vi.stubGlobal("ResizeObserver", ResizeObserverStub);
});

afterEach(() => {
  cleanup();
});

describe("ScreenerPage more-filters popover", () => {
  it("is closed until the button is clicked", () => {
    renderScreener();
    expect(screen.queryByRole("dialog", { name: "screener.more_filters" })).toBeNull();
    expect(moreFiltersButton()).toHaveAttribute("aria-expanded", "false");
  });

  it("opens inside the header on click, with the debt window select", () => {
    renderScreener();
    fireEvent.click(moreFiltersButton());

    const popover = screen.getByRole("dialog", { name: "screener.more_filters" });
    expect(popover).toHaveClass("screener-filter-popover");
    expect(popover.closest(".screener-header")).not.toBeNull();
    expect(moreFiltersButton()).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByLabelText("screener.debt_window")).toBeInTheDocument();
  });

  it("closes on a second click", () => {
    renderScreener();
    fireEvent.click(moreFiltersButton());
    fireEvent.click(moreFiltersButton());
    expect(screen.queryByRole("dialog", { name: "screener.more_filters" })).toBeNull();
  });

  it("closes on Escape", () => {
    renderScreener();
    fireEvent.click(moreFiltersButton());
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog", { name: "screener.more_filters" })).toBeNull();
  });

  it("closes on a click outside the header", () => {
    renderScreener();
    fireEvent.click(moreFiltersButton());
    fireEvent.mouseDown(document.body);
    expect(screen.queryByRole("dialog", { name: "screener.more_filters" })).toBeNull();
  });
});
