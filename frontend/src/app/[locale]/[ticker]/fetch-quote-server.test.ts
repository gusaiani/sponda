import { describe, it, expect, vi, beforeEach } from "vitest";

const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

/** Headers the incoming request is pretending to carry. */
let incomingHeaders = new Headers();

/** Simulates being called outside a request scope, where headers() throws. */
let headersUnavailable = false;

vi.mock("next/headers", () => ({
  headers: async () => {
    if (headersUnavailable) throw new Error("outside request scope");
    return incomingHeaders;
  },
}));

function forwardedHeaders(): Headers {
  const [, init] = mockFetch.mock.calls[0];
  return new Headers((init as RequestInit).headers);
}

describe("fetchQuoteServer", () => {
  beforeEach(() => {
    mockFetch.mockReset();
    incomingHeaders = new Headers();
    headersUnavailable = false;
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
    mockFetch.mockRejectedValue(new Error("network failure"));

    const { fetchQuoteServer } = await import("./fetch-quote-server");
    const result = await fetchQuoteServer("PETR4");
    expect(result.error).toBe("server-error");
    expect(result.data).toBeNull();
  });

  describe("client IP forwarding", () => {
    // Without this, Django's client_ip() finds no CF-Connecting-IP and no
    // X-Forwarded-For and falls through to REMOTE_ADDR = 127.0.0.1, so every
    // server-rendered company page in production shares ONE anonymous
    // lookup bucket of SPONDA_ANON_LOOKUPS_PER_DAY distinct tickers per day.
    // Past that, the SSR fetch 429s and the page silently degrades to
    // client-side fetching.
    it("forwards CF-Connecting-IP so the lookup cap is attributed to the visitor", async () => {
      incomingHeaders = new Headers({ "cf-connecting-ip": "203.0.113.7" });
      mockFetch.mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({}) });

      const { fetchQuoteServer } = await import("./fetch-quote-server");
      await fetchQuoteServer("PETR4");

      expect(forwardedHeaders().get("cf-connecting-ip")).toBe("203.0.113.7");
    });

    it("forwards X-Forwarded-For, which nginx sets when Cloudflare is not in front", async () => {
      incomingHeaders = new Headers({ "x-forwarded-for": "203.0.113.7, 10.0.0.1" });
      mockFetch.mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({}) });

      const { fetchQuoteServer } = await import("./fetch-quote-server");
      await fetchQuoteServer("PETR4");

      expect(forwardedHeaders().get("x-forwarded-for")).toBe("203.0.113.7, 10.0.0.1");
    });

    it("sends no IP header when the incoming request has none", async () => {
      mockFetch.mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({}) });

      const { fetchQuoteServer } = await import("./fetch-quote-server");
      await fetchQuoteServer("PETR4");

      const sent = forwardedHeaders();
      expect(sent.get("cf-connecting-ip")).toBeNull();
      expect(sent.get("x-forwarded-for")).toBeNull();
    });

    it("forwards no cookie, so the fetch stays anonymous", async () => {
      incomingHeaders = new Headers({
        "cf-connecting-ip": "203.0.113.7",
        cookie: "sessionid=secret",
      });
      mockFetch.mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({}) });

      const { fetchQuoteServer } = await import("./fetch-quote-server");
      await fetchQuoteServer("PETR4");

      expect(forwardedHeaders().get("cookie")).toBeNull();
    });

    it("still resolves when headers() is unavailable", async () => {
      // Route handlers and static generation can call this outside a request
      // scope. A missing header store must not take the page down.
      headersUnavailable = true;
      mockFetch.mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({}) });

      const { fetchQuoteServer } = await import("./fetch-quote-server");
      const result = await fetchQuoteServer("PETR4");

      expect(result.error).toBeNull();
    });
  });
});
describe("transport failures", () => {
  beforeEach(() => {
    mockFetch.mockReset();
    incomingHeaders = new Headers();
    headersUnavailable = false;
  });

  it("retries once when the connection dies mid-parse", async () => {
    // gunicorn closes the connection on every response and Node's HTTP
    // client intermittently fails to parse that, which is what turned
    // lookup-cap 429s into 500s.
    const parseError = new Error("Parse Error: Data after `Connection: close`");
    mockFetch
      .mockRejectedValueOnce(parseError)
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ pe10: 7 }) });

    const { fetchQuoteServer } = await import("./fetch-quote-server");
    const result = await fetchQuoteServer("PETR4");

    expect(mockFetch).toHaveBeenCalledTimes(2);
    expect(result.error).toBeNull();
    expect(result.data?.pe10).toBe(7);
  });

  it("still reports server-error when both attempts fail", async () => {
    mockFetch.mockRejectedValue(new Error("network failure"));

    const { fetchQuoteServer } = await import("./fetch-quote-server");
    const result = await fetchQuoteServer("PETR4");

    expect(result.error).toBe("server-error");
  });

  it("does not retry a 429, which is an answer rather than a failure", async () => {
    mockFetch.mockResolvedValueOnce({ ok: false, status: 429 });

    const { fetchQuoteServer } = await import("./fetch-quote-server");
    const result = await fetchQuoteServer("PETR4");

    expect(mockFetch).toHaveBeenCalledOnce();
    expect(result.error).toBe("server-error");
  });
});
