import { describe, it, expect, vi, afterEach } from "vitest";
import { fetchPeersServer } from "./fetch-peers-server";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("fetchPeersServer", () => {
  it("returns the peers Django lists for the company", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => [{ symbol: "ITUB4", name: "Itaú" }],
    }));
    vi.stubGlobal("fetch", fetchMock);

    expect(await fetchPeersServer("BBAS3")).toEqual([{ symbol: "ITUB4", name: "Itaú" }]);
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, { next?: { revalidate?: number } }];
    expect(url).toMatch(/\/api\/tickers\/BBAS3\/peers\/$/);
    expect(init.next?.revalidate).toBeGreaterThan(0);
  });

  it("returns an empty list when Django answers with an error", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: false, json: async () => ({}) })));
    expect(await fetchPeersServer("BBAS3")).toEqual([]);
  });

  it("returns an empty list when the request throws", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new Error("ECONNREFUSED"); }));
    expect(await fetchPeersServer("BBAS3")).toEqual([]);
  });

  it("drops entries that are not peers", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, json: async () => ({ detail: "Not found" }) })));
    expect(await fetchPeersServer("NOPE")).toEqual([]);
  });
});
