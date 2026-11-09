// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach, beforeAll } from "vitest";
import { render, cleanup } from "@testing-library/react";
import {
  IsRestoringProvider,
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";
import { renderToString } from "react-dom/server";
import type { ReactNode } from "react";
import { ListCard } from "./ListCard";
import { batchQueryKey } from "../hooks/useQuotesBatch";

/*
 * The server renders a list card whose batch query has no data yet as
 * "loading". On the browser's first pass the persisted cache is still
 * being restored, and React Query reports that pending query as idle,
 * so `isLoading` is false there. React does not patch a className that
 * differs during hydration, so the card kept the server's half-opacity
 * class forever, even after its numbers arrived. The loading look must
 * therefore depend on the data, which is the same on both sides.
 */

beforeAll(() => {
  class ResizeObserverStub {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  globalThis.ResizeObserver = ResizeObserverStub as unknown as typeof ResizeObserver;
});

afterEach(cleanup);

// The quote's own derivation is covered elsewhere; here the card only
// needs to see that a quote exists.
vi.mock(import("../hooks/deriveForYears"), async (importOriginal) => ({
  ...(await importOriginal()),
  deriveForYears: (quote) => quote,
}));

vi.mock("../i18n", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    locale: "pt",
  }),
}));

const LIST_TICKERS = ["DEXP4", "PETR4"];
const LOADING_CLASS = "list-card-loading";

function quoteFor(ticker: string) {
  return {
    ticker,
    pe10: 5.6,
    pfcf10: 11.3,
    peg: null,
    earningsCAGR: -2.3,
    debtToEquity: 0.24,
    roe: 15.3,
  };
}

function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
}

function withProviders(
  queryClient: QueryClient,
  isRestoring: boolean,
  children: ReactNode,
) {
  return (
    <QueryClientProvider client={queryClient}>
      <IsRestoringProvider value={isRestoring}>{children}</IsRestoringProvider>
    </QueryClientProvider>
  );
}

function listCard() {
  return <ListCard listId={1} name="Poema" tickers={LIST_TICKERS} years={10} />;
}

function cardClassName(container: HTMLElement): string {
  return container.querySelector(".list-card")?.className ?? "";
}

describe("ListCard loading look", () => {
  it("matches the server's first paint while the persisted cache is restoring", () => {
    const serverMarkup = renderToString(
      withProviders(createQueryClient(), false, listCard()),
    );
    const serverHasLoadingClass = serverMarkup.includes(LOADING_CLASS);

    const { container } = render(
      withProviders(createQueryClient(), true, listCard()),
    );

    expect(cardClassName(container).includes(LOADING_CLASS)).toBe(
      serverHasLoadingClass,
    );
  });

  it("drops the loading look once the list's quotes are in the cache", () => {
    const queryClient = createQueryClient();
    queryClient.setQueryData(batchQueryKey(LIST_TICKERS), {
      results: {
        DEXP4: { quote: quoteFor("DEXP4") },
        PETR4: { quote: quoteFor("PETR4") },
      },
    });

    const { container } = render(withProviders(queryClient, true, listCard()));

    expect(cardClassName(container)).not.toContain(LOADING_CLASS);
  });

  it("drops the loading look when the batch request failed", async () => {
    const queryClient = createQueryClient();
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response("boom", { status: 500 }));

    const { container, findByText } = render(
      withProviders(queryClient, false, listCard()),
    );
    await findByText("Poema");
    await vi.waitFor(() => {
      expect(cardClassName(container)).not.toContain(LOADING_CLASS);
    });

    fetchMock.mockRestore();
  });
});
