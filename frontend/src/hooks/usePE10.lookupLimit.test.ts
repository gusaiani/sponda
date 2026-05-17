import { describe, it, expect, vi, afterEach } from "vitest";
import {
  fetchQuote,
  LookupLimitError,
  resolveLookupLimitAction,
} from "./usePE10";

function mockFetchResponse(status: number, body: unknown) {
  return vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    text: async () => JSON.stringify(body),
    json: async () => body,
  } as unknown as Response);
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("fetchQuote — lookup limit", () => {
  it("throws LookupLimitError carrying scope + limit on 429 lookup_limit", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetchResponse(429, {
        error: "lookup_limit_reached",
        code: "lookup_limit",
        limit: 20,
        scope: "anonymous",
      }),
    );
    await expect(fetchQuote("PETR4")).rejects.toBeInstanceOf(LookupLimitError);
    try {
      await fetchQuote("PETR4");
    } catch (e) {
      const err = e as LookupLimitError;
      expect(err.scope).toBe("anonymous");
      expect(err.limit).toBe(20);
    }
  });

  it("throws a plain Error (not LookupLimitError) on a normal 404", async () => {
    vi.stubGlobal("fetch", mockFetchResponse(404, { error: "not found" }));
    await expect(fetchQuote("NOPE")).rejects.not.toBeInstanceOf(
      LookupLimitError,
    );
  });

  it("does not treat a generic 429 without the code as a lookup limit", async () => {
    vi.stubGlobal("fetch", mockFetchResponse(429, { error: "slow down" }));
    await expect(fetchQuote("PETR4")).rejects.not.toBeInstanceOf(
      LookupLimitError,
    );
  });
});

describe("resolveLookupLimitAction", () => {
  it("anonymous scope -> open auth modal", () => {
    const action = resolveLookupLimitAction(
      new LookupLimitError("anonymous", 20),
    );
    expect(action).toEqual({ kind: "auth-modal", limit: 20 });
  });

  it("unverified scope -> show email verification prompt", () => {
    const action = resolveLookupLimitAction(
      new LookupLimitError("unverified", 50),
    );
    expect(action).toEqual({ kind: "verify-prompt", limit: 50 });
  });

  it("non-limit errors -> no action", () => {
    expect(resolveLookupLimitAction(new Error("boom"))).toBeNull();
    expect(resolveLookupLimitAction(undefined)).toBeNull();
  });
});
