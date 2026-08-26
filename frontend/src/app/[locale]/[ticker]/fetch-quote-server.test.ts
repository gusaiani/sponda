import { describe, it, expect, vi, beforeEach } from "vitest";

const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

const incomingHeaders = vi.hoisted(() => ({ current: new Headers() }));

vi.mock("next/headers", () => ({
  headers: async () => incomingHeaders.current,
}));

describe("fetchQuoteServer", () => {
  beforeEach(() => {
    mockFetch.mockReset();
    incomingHeaders.current = new Headers();
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

/**
 * The lookup cap is scoped by hashed client IP. A Server Component fetch
 * opens a fresh connection from the Node process, so without this every
 * server-rendered quote on the site shared one anonymous bucket of twenty
 * tickers a day. Past the twentieth, every ticker page server-rendered an
 * empty skeleton.
 */
describe("fetchQuoteServer request attribution", () => {
  beforeEach(() => {
    mockFetch.mockReset();
    incomingHeaders.current = new Headers();
    mockFetch.mockResolvedValue({ ok: true, status: 200, json: async () => ({}) });
  });

  it("bills the lookup to the visitor's address, not to the Node process", async () => {
    incomingHeaders.current = new Headers({ "x-forwarded-for": "203.0.113.7" });

    const { fetchQuoteServer } = await import("./fetch-quote-server");
    await fetchQuoteServer("PAM");

    const [, init] = mockFetch.mock.calls[0];
    const sentHeaders = new Headers((init as RequestInit).headers);
    expect(sentHeaders.get("x-forwarded-for")).toBe("203.0.113.7");
  });

  it("forwards the session cookie so a verified reader gets an uncapped render", async () => {
    incomingHeaders.current = new Headers({ cookie: "sessionid=abc" });

    const { fetchQuoteServer } = await import("./fetch-quote-server");
    await fetchQuoteServer("PAM");

    const [, init] = mockFetch.mock.calls[0];
    const sentHeaders = new Headers((init as RequestInit).headers);
    expect(sentHeaders.get("cookie")).toBe("sessionid=abc");
  });
});

describe("fetchQuoteServer address forwarding", () => {
  beforeEach(() => {
    mockFetch.mockReset();
    incomingHeaders.current = new Headers();
    mockFetch.mockResolvedValue({ ok: true, status: 200, json: async () => ({}) });
  });

  it("forwards CF-Connecting-IP, which client_ip() reads before anything else", async () => {
    // Cloudflare overwrites this on every request, so it is the one address
    // header that cannot be spoofed from outside.
    incomingHeaders.current = new Headers({ "cf-connecting-ip": "203.0.113.7" });

    const { fetchQuoteServer } = await import("./fetch-quote-server");
    await fetchQuoteServer("PETR4");

    const [, init] = mockFetch.mock.calls[0];
    expect(new Headers((init as RequestInit).headers).get("cf-connecting-ip"))
      .toBe("203.0.113.7");
  });

  it("sends no address header when the incoming request carries none", async () => {
    const { fetchQuoteServer } = await import("./fetch-quote-server");
    await fetchQuoteServer("PETR4");

    const sent = new Headers((mockFetch.mock.calls[0][1] as RequestInit).headers);
    expect(sent.get("cf-connecting-ip")).toBeNull();
    expect(sent.get("x-forwarded-for")).toBeNull();
  });
});

describe("fetchQuoteServer transport failures", () => {
  beforeEach(() => {
    mockFetch.mockReset();
    incomingHeaders.current = new Headers();
  });

  it("retries once when the connection dies mid-parse", async () => {
    // gunicorn's sync workers close the connection on every response and
    // Node's HTTP client intermittently fails to parse that.
    mockFetch
      .mockRejectedValueOnce(new Error("Parse Error: Data after `Connection: close`"))
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ pe10: 7 }) });

    const { fetchQuoteServer } = await import("./fetch-quote-server");
    const result = await fetchQuoteServer("PETR4");

    expect(mockFetch).toHaveBeenCalledTimes(2);
    expect(result.data?.pe10).toBe(7);
  });

  it("still reports server-error when both attempts fail", async () => {
    mockFetch.mockRejectedValue(new Error("network failure"));

    const { fetchQuoteServer } = await import("./fetch-quote-server");
    expect((await fetchQuoteServer("PETR4")).error).toBe("server-error");
  });

  it("does not retry a 429, which is an answer rather than a failure", async () => {
    mockFetch.mockResolvedValueOnce({ ok: false, status: 429 });

    const { fetchQuoteServer } = await import("./fetch-quote-server");
    const result = await fetchQuoteServer("PETR4");

    expect(mockFetch).toHaveBeenCalledOnce();
    expect(result.error).toBe("server-error");
  });
});
