// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { usePeers } from "./usePeers";

function wrapper({ children }: { children: React.ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("usePeers", () => {
  it("fetches the peers when the server passed none", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => [{ symbol: "ITUB4", name: "Itaú" }],
    }));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => usePeers("BBAS3"), { wrapper });

    await waitFor(() => expect(result.current.data).toEqual([{ symbol: "ITUB4", name: "Itaú" }]));
    expect(fetchMock).toHaveBeenCalledWith("/api/tickers/BBAS3/peers/", { credentials: "include" });
  });

  it("starts from the server-rendered peers without a round trip", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const initialPeers = [{ symbol: "ITUB4", name: "Itaú" }];

    const { result } = renderHook(() => usePeers("BBAS3", initialPeers), { wrapper });

    expect(result.current.data).toEqual(initialPeers);
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("treats an empty server list as unknown and still fetches", async () => {
    // The server helper returns [] on any failure; that must not pin the
    // client to an empty list for the hour the query stays fresh.
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => [{ symbol: "ITUB4", name: "Itaú" }],
    }));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => usePeers("BBAS3", []), { wrapper });

    await waitFor(() => expect(result.current.data).toEqual([{ symbol: "ITUB4", name: "Itaú" }]));
  });
});
