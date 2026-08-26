import { describe, it, expect, vi, afterEach } from "vitest";
import { fetchFromDjango } from "./django-fetch";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

/** The exact failure seen in production, from Node's HTTP parser. */
function parseError() {
  const error = new Error("Parse Error: Data after `Connection: close`");
  (error as Error & { code?: string }).code = "HPE_CLOSED_CONNECTION";
  return error;
}

describe("fetchFromDjango", () => {
  it("returns the response when the first attempt works", async () => {
    const fetchMock = vi.fn(async () => new Response("ok", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const response = await fetchFromDjango("http://localhost:8710/api/quote/PETR4/");

    expect(response?.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledOnce();
  });

  it("retries once when the connection dies mid-parse", async () => {
    // gunicorn's sync workers close the connection on every response and
    // Node's client intermittently fails to parse that. A second attempt
    // gets a fresh socket and succeeds.
    const fetchMock = vi.fn()
      .mockRejectedValueOnce(parseError())
      .mockResolvedValueOnce(new Response("ok", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const response = await fetchFromDjango("http://localhost:8710/api/quote/PETR4/");

    expect(response?.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("gives up after one retry rather than hammering a downed backend", async () => {
    const fetchMock = vi.fn().mockRejectedValue(parseError());
    vi.stubGlobal("fetch", fetchMock);

    expect(await fetchFromDjango("http://localhost:8710/api/quote/PETR4/")).toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("does not retry an HTTP error status", async () => {
    // A 429 is an answer, not a transport failure. Retrying it would burn a
    // second round trip to be told the same thing, and would mask the status
    // the caller needs to act on.
    const fetchMock = vi.fn(async () => new Response("", { status: 429 }));
    vi.stubGlobal("fetch", fetchMock);

    const response = await fetchFromDjango("http://localhost:8710/api/quote/PETR4/");

    expect(response?.status).toBe(429);
    expect(fetchMock).toHaveBeenCalledOnce();
  });

  it("never retries a non-idempotent method", async () => {
    // Replaying a POST could double-write.
    const fetchMock = vi.fn().mockRejectedValue(parseError());
    vi.stubGlobal("fetch", fetchMock);

    expect(await fetchFromDjango("http://localhost:8710/api/x/", { method: "POST" })).toBeNull();
    expect(fetchMock).toHaveBeenCalledOnce();
  });

  it("retries a HEAD, which is idempotent", async () => {
    const fetchMock = vi.fn()
      .mockRejectedValueOnce(parseError())
      .mockResolvedValueOnce(new Response("", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await fetchFromDjango("http://localhost:8710/api/x/", { method: "HEAD" });

    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("passes the caller's init through unchanged", async () => {
    const fetchMock = vi.fn(async (_url: unknown, init: unknown) => {
      void _url;
      void init;
      return new Response("ok", { status: 200 });
    });
    vi.stubGlobal("fetch", fetchMock);

    await fetchFromDjango("http://localhost:8710/api/x/", { next: { revalidate: 900 } });

    const init = fetchMock.mock.calls[0][1] as { next?: { revalidate?: number } };
    expect(init.next?.revalidate).toBe(900);
  });
});
