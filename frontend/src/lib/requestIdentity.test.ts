import { describe, it, expect, vi, beforeEach } from "vitest";

const incomingHeaders = vi.hoisted(() => ({ current: new Headers() }));

vi.mock("next/headers", () => ({
  headers: async () => incomingHeaders.current,
}));

import { requestIdentityHeaders } from "./requestIdentity";

beforeEach(() => {
  incomingHeaders.current = new Headers();
});

describe("requestIdentityHeaders", () => {
  it("forwards the visitor's cookies so a signed-in reader stays signed in", async () => {
    incomingHeaders.current = new Headers({ cookie: "sessionid=abc; locale=pt" });

    const identity = await requestIdentityHeaders();

    expect(identity.get("cookie")).toBe("sessionid=abc; locale=pt");
  });

  it("forwards the forwarded-for chain so Django sees the visitor, not the Node process", async () => {
    incomingHeaders.current = new Headers({ "x-forwarded-for": "203.0.113.7" });

    const identity = await requestIdentityHeaders();

    expect(identity.get("x-forwarded-for")).toBe("203.0.113.7");
  });

  it("forwards Cloudflare's client address, which Django reads first", async () => {
    incomingHeaders.current = new Headers({
      "cf-connecting-ip": "203.0.113.7",
      "x-forwarded-for": "198.51.100.1",
    });

    const identity = await requestIdentityHeaders();

    expect(identity.get("cf-connecting-ip")).toBe("203.0.113.7");
    expect(identity.get("x-forwarded-for")).toBe("198.51.100.1");
  });

  it("sets nothing when the request carries no identity at all", async () => {
    const identity = await requestIdentityHeaders();

    expect([...identity.keys()]).toEqual([]);
  });
});
