import { describe, it, expect, vi, beforeEach } from "vitest";

const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

describe("fetchQuoteServer", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it("fetches without revalidate so prices are never served stale from Next.js ISR cache", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ pe10: 20, marketCap: 500_000_000 }),
    });

    const { fetchQuoteServer } = await import("./fetch-quote-server");
    await fetchQuoteServer("PETR4");

    expect(mockFetch).toHaveBeenCalledOnce();
    const [, init] = mockFetch.mock.calls[0];
    expect((init as RequestInit & { next?: { revalidate?: number } }).next?.revalidate).toBeUndefined();
    expect((init as RequestInit & { cache?: string }).cache).toBe("no-store");
  });

  it("returns data on success", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ pe10: 25, marketCap: 1_000_000_000 }),
    });

    const { fetchQuoteServer } = await import("./fetch-quote-server");
    const result = await fetchQuoteServer("VALE3");
    expect(result.error).toBeNull();
    expect(result.data?.pe10).toBe(25);
  });

  it("returns not-found error on 404", async () => {
    mockFetch.mockResolvedValueOnce({ ok: false, status: 404 });

    const { fetchQuoteServer } = await import("./fetch-quote-server");
    const result = await fetchQuoteServer("UNKNOWN");
    expect(result.error).toBe("not-found");
    expect(result.data).toBeNull();
  });

  it("returns server-error on non-ok response", async () => {
    mockFetch.mockResolvedValueOnce({ ok: false, status: 500 });

    const { fetchQuoteServer } = await import("./fetch-quote-server");
    const result = await fetchQuoteServer("PETR4");
    expect(result.error).toBe("server-error");
    expect(result.data).toBeNull();
  });

  it("returns server-error when fetch throws", async () => {
    mockFetch.mockRejectedValueOnce(new Error("network failure"));

    const { fetchQuoteServer } = await import("./fetch-quote-server");
    const result = await fetchQuoteServer("PETR4");
    expect(result.error).toBe("server-error");
    expect(result.data).toBeNull();
  });
});
