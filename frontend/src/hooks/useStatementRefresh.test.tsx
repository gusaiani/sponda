// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import React from "react";
import { act, renderHook } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToString } from "react-dom/server";
import {
  MAX_STATUS_POLLS,
  STATUS_POLL_INTERVAL_MS,
  useStatementRefresh,
} from "./useStatementRefresh";

/**
 * A payload flagged `refreshPending` was computed from stored statements
 * while a background job refetches them. The hook polls the status
 * endpoint, and once the job is done it invalidates the three payloads so
 * the page swaps the refreshed numbers in without a reload.
 */

const TICKER = "PAM";
const OTHER_TICKER = "YPF";

function statusUrl(ticker: string): string {
  return `/api/quote/${ticker}/refresh-status/`;
}

function statusResponse(refreshPending: boolean): Response {
  return new Response(JSON.stringify({ refreshPending }), { status: 200 });
}

function invalidatedKeys(spy: ReturnType<typeof vi.spyOn>): unknown[] {
  const calls = spy.mock.calls as Array<[{ queryKey: unknown }]>;
  return calls.map(([filters]) => filters.queryKey);
}

let queryClient: QueryClient;
let invalidateSpy: ReturnType<typeof vi.spyOn>;
let fetchMock: ReturnType<typeof vi.fn>;

function wrapper({ children }: { children: React.ReactNode }) {
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

function renderStatementRefresh(ticker: string, isRefreshPending: boolean) {
  return renderHook(
    (props: { ticker: string; isRefreshPending: boolean }) =>
      useStatementRefresh(props.ticker, props.isRefreshPending),
    { wrapper, initialProps: { ticker, isRefreshPending } },
  );
}

async function advanceOneInterval() {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(STATUS_POLL_INTERVAL_MS);
  });
}

beforeEach(() => {
  vi.useFakeTimers();
  queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
  fetchMock = vi.fn().mockImplementation(async () => statusResponse(true));
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("useStatementRefresh", () => {
  it("does not poll when nothing is pending", async () => {
    const { result } = renderStatementRefresh(TICKER, false);

    await advanceOneInterval();
    await advanceOneInterval();

    expect(fetchMock).not.toHaveBeenCalled();
    expect(result.current.isRefreshing).toBe(false);
  });

  it("renders as not refreshing on the server, whatever the payload says", () => {
    function Probe() {
      const { isRefreshing } = useStatementRefresh(TICKER, true);
      return <span>{isRefreshing ? "refreshing" : "idle"}</span>;
    }

    const html = renderToString(
      <QueryClientProvider client={queryClient}>
        <Probe />
      </QueryClientProvider>,
    );

    expect(html).toContain("idle");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("waits one interval before the first poll, with the status cache disabled", async () => {
    renderStatementRefresh(TICKER, true);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(STATUS_POLL_INTERVAL_MS - 1);
    });
    expect(fetchMock).not.toHaveBeenCalled();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith(
      statusUrl(TICKER),
      expect.objectContaining({ cache: "no-store" }),
    );
  });

  it("polls once per interval while the refresh is still pending", async () => {
    renderStatementRefresh(TICKER, true);

    await advanceOneInterval();
    await advanceOneInterval();
    await advanceOneInterval();

    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(invalidateSpy).not.toHaveBeenCalled();
  });

  it("reports refreshing from the moment polling starts", async () => {
    const { result } = renderStatementRefresh(TICKER, true);

    expect(result.current.isRefreshing).toBe(true);
  });

  it("invalidates the quote, fundamentals and history payloads when the status flips to false", async () => {
    fetchMock
      .mockImplementationOnce(async () => statusResponse(true))
      .mockImplementationOnce(async () => statusResponse(false));
    renderStatementRefresh(TICKER, true);

    await advanceOneInterval();
    expect(invalidateSpy).not.toHaveBeenCalled();

    await advanceOneInterval();
    expect(invalidatedKeys(invalidateSpy)).toEqual(
      expect.arrayContaining([
        ["pe10", TICKER],
        ["fundamentals", TICKER],
        ["multiples-history", TICKER],
      ]),
    );
    expect(invalidateSpy).toHaveBeenCalledTimes(3);
  });

  it("keeps reporting refreshing until the refetches settle", async () => {
    const pendingRefetches: Array<() => void> = [];
    invalidateSpy.mockImplementation(
      () => new Promise<void>((resolve) => { pendingRefetches.push(resolve); }),
    );
    fetchMock.mockImplementation(async () => statusResponse(false));
    const { result } = renderStatementRefresh(TICKER, true);

    await advanceOneInterval();
    expect(result.current.isRefreshing).toBe(true);

    await act(async () => {
      pendingRefetches.forEach((settleRefetch) => settleRefetch());
    });
    expect(result.current.isRefreshing).toBe(false);
  });

  it("stops polling after the cycle ends", async () => {
    fetchMock.mockImplementation(async () => statusResponse(false));
    renderStatementRefresh(TICKER, true);

    await advanceOneInterval();
    await advanceOneInterval();
    await advanceOneInterval();

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("keeps polling after a network failure", async () => {
    fetchMock
      .mockImplementationOnce(async () => { throw new TypeError("network down"); })
      .mockImplementationOnce(async () => statusResponse(false));
    renderStatementRefresh(TICKER, true);

    await advanceOneInterval();
    expect(invalidateSpy).not.toHaveBeenCalled();

    await advanceOneInterval();
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(invalidateSpy).toHaveBeenCalledTimes(3);
  });

  it("keeps polling after a non-OK response", async () => {
    fetchMock
      .mockImplementationOnce(async () => new Response("{}", { status: 500 }))
      .mockImplementationOnce(async () => statusResponse(false));
    renderStatementRefresh(TICKER, true);

    await advanceOneInterval();
    expect(invalidateSpy).not.toHaveBeenCalled();

    await advanceOneInterval();
    expect(invalidateSpy).toHaveBeenCalledTimes(3);
  });

  it("counts failed polls toward the limit", async () => {
    fetchMock.mockImplementation(async () => { throw new TypeError("network down"); });
    const { result } = renderStatementRefresh(TICKER, true);

    for (let poll = 0; poll < MAX_STATUS_POLLS + 5; poll += 1) {
      await advanceOneInterval();
    }

    expect(fetchMock).toHaveBeenCalledTimes(MAX_STATUS_POLLS);
    expect(result.current.isRefreshing).toBe(false);
  });

  it("gives up quietly after the maximum number of polls", async () => {
    const { result } = renderStatementRefresh(TICKER, true);

    for (let poll = 0; poll < MAX_STATUS_POLLS - 1; poll += 1) {
      await advanceOneInterval();
    }
    expect(result.current.isRefreshing).toBe(true);

    await advanceOneInterval();
    expect(fetchMock).toHaveBeenCalledTimes(MAX_STATUS_POLLS);
    expect(result.current.isRefreshing).toBe(false);
    expect(invalidateSpy).not.toHaveBeenCalled();

    await advanceOneInterval();
    expect(fetchMock).toHaveBeenCalledTimes(MAX_STATUS_POLLS);
  });

  it("does not restart polling when a payload arrives flagged pending after the cycle ended", async () => {
    fetchMock.mockImplementation(async () => statusResponse(false));
    const { result, rerender } = renderStatementRefresh(TICKER, true);
    await advanceOneInterval();
    rerender({ ticker: TICKER, isRefreshPending: false });

    rerender({ ticker: TICKER, isRefreshPending: true });
    await advanceOneInterval();
    await advanceOneInterval();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(result.current.isRefreshing).toBe(false);
  });

  it("does not restart polling after giving up", async () => {
    const { rerender } = renderStatementRefresh(TICKER, true);
    for (let poll = 0; poll < MAX_STATUS_POLLS; poll += 1) {
      await advanceOneInterval();
    }
    rerender({ ticker: TICKER, isRefreshPending: false });

    rerender({ ticker: TICKER, isRefreshPending: true });
    await advanceOneInterval();

    expect(fetchMock).toHaveBeenCalledTimes(MAX_STATUS_POLLS);
  });

  it("finishes the cycle even when the payloads stop being pending mid-flight", async () => {
    fetchMock
      .mockImplementationOnce(async () => statusResponse(true))
      .mockImplementationOnce(async () => statusResponse(false));
    const { result, rerender } = renderStatementRefresh(TICKER, true);
    await advanceOneInterval();

    rerender({ ticker: TICKER, isRefreshPending: false });
    await advanceOneInterval();

    expect(invalidateSpy).toHaveBeenCalledTimes(3);
    expect(result.current.isRefreshing).toBe(false);
  });

  it("starts a fresh cycle for a different ticker", async () => {
    fetchMock.mockImplementation(async () => statusResponse(false));
    const { result, rerender } = renderStatementRefresh(TICKER, true);
    await advanceOneInterval();
    expect(result.current.isRefreshing).toBe(false);

    rerender({ ticker: OTHER_TICKER, isRefreshPending: true });
    expect(result.current.isRefreshing).toBe(true);
    await advanceOneInterval();

    expect(fetchMock).toHaveBeenLastCalledWith(statusUrl(OTHER_TICKER), expect.anything());
    expect(invalidatedKeys(invalidateSpy)).toContainEqual(["pe10", OTHER_TICKER]);
  });

  it("abandons the old ticker's polling when the ticker changes", async () => {
    const { rerender } = renderStatementRefresh(TICKER, true);
    await advanceOneInterval();
    fetchMock.mockClear();

    rerender({ ticker: OTHER_TICKER, isRefreshPending: false });
    await advanceOneInterval();
    await advanceOneInterval();

    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("does not let a stale poll invalidate the new ticker's data", async () => {
    let resolveStalePoll: (response: Response) => void = () => {};
    fetchMock.mockImplementationOnce(
      () => new Promise<Response>((resolve) => { resolveStalePoll = resolve; }),
    );
    const { rerender } = renderStatementRefresh(TICKER, true);
    await advanceOneInterval();

    rerender({ ticker: OTHER_TICKER, isRefreshPending: false });
    await act(async () => {
      resolveStalePoll(statusResponse(false));
    });

    expect(invalidateSpy).not.toHaveBeenCalled();
  });

  it("clears its timer on unmount", async () => {
    const { unmount } = renderStatementRefresh(TICKER, true);

    unmount();
    await advanceOneInterval();
    await advanceOneInterval();

    expect(fetchMock).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("does not invalidate when unmounted while a poll is in flight", async () => {
    let resolveInFlightPoll: (response: Response) => void = () => {};
    fetchMock.mockImplementationOnce(
      () => new Promise<Response>((resolve) => { resolveInFlightPoll = resolve; }),
    );
    const { unmount } = renderStatementRefresh(TICKER, true);
    await advanceOneInterval();

    unmount();
    await act(async () => {
      resolveInFlightPoll(statusResponse(false));
    });

    expect(invalidateSpy).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);
  });
});
