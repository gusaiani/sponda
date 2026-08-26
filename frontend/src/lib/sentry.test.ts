import { describe, it, expect, vi } from "vitest";

import { initSentry } from "./sentry";

describe("initSentry", () => {
  it("is a no-op when dsn is undefined", () => {
    const sdk = { init: vi.fn() };
    const result = initSentry(sdk, {
      dsn: undefined,
      environment: "development",
      release: "abc",
    });
    expect(result).toBe(false);
    expect(sdk.init).not.toHaveBeenCalled();
  });

  it("is a no-op when dsn is empty string", () => {
    const sdk = { init: vi.fn() };
    const result = initSentry(sdk, {
      dsn: "",
      environment: "development",
      release: "abc",
    });
    expect(result).toBe(false);
    expect(sdk.init).not.toHaveBeenCalled();
  });

  it("calls sdk.init with expected options when dsn is provided", () => {
    const sdk = { init: vi.fn() };
    const result = initSentry(sdk, {
      dsn: "https://public@o0.ingest.sentry.io/0",
      environment: "production",
      release: "deadbeef",
      tracesSampleRate: 0.5,
      replaysSessionSampleRate: 0.1,
      replaysOnErrorSampleRate: 1.0,
    });
    expect(result).toBe(true);
    expect(sdk.init).toHaveBeenCalledTimes(1);
    const options = sdk.init.mock.calls[0][0];
    expect(options.dsn).toBe("https://public@o0.ingest.sentry.io/0");
    expect(options.environment).toBe("production");
    expect(options.release).toBe("deadbeef");
    expect(options.tracesSampleRate).toBe(0.5);
    expect(options.replaysSessionSampleRate).toBe(0.1);
    expect(options.replaysOnErrorSampleRate).toBe(1.0);
    expect(options.sendDefaultPii).toBe(false);
  });

  it("uses sensible default sample rates when not provided", () => {
    const sdk = { init: vi.fn() };
    initSentry(sdk, {
      dsn: "https://public@o0.ingest.sentry.io/0",
      environment: "production",
      release: "abc",
    });
    const options = sdk.init.mock.calls[0][0];
    expect(options.tracesSampleRate).toBe(0.2);
    expect(options.replaysSessionSampleRate).toBe(0.1);
    expect(options.replaysOnErrorSampleRate).toBe(1.0);
  });

  it("forwards tracePropagationTargets when provided", () => {
    const sdk = { init: vi.fn() };
    initSentry(sdk, {
      dsn: "https://public@o0.ingest.sentry.io/0",
      environment: "production",
      release: "abc",
      tracePropagationTargets: ["localhost", /^https:\/\/sponda\.capital/],
    });
    const options = sdk.init.mock.calls[0][0];
    expect(options.tracePropagationTargets).toEqual([
      "localhost",
      /^https:\/\/sponda\.capital/,
    ]);
  });

  it("uses tracesSampler when provided, overriding tracesSampleRate", () => {
    const sdk = { init: vi.fn() };
    const tracesSampler = vi.fn().mockReturnValue(0.5);
    initSentry(sdk, {
      dsn: "https://public@o0.ingest.sentry.io/0",
      environment: "production",
      release: "abc",
      tracesSampler,
    });
    const options = sdk.init.mock.calls[0][0];
    expect(options.tracesSampler).toBe(tracesSampler);
  });
});

describe("initSentry noise filtering", () => {
  const init = (overrides = {}) => {
    const sdk = { init: vi.fn() };
    initSentry(sdk, {
      dsn: "https://public@o0.ingest.sentry.io/0",
      environment: "production",
      release: "deadbeef",
      ...overrides,
    });
    return sdk.init.mock.calls[0][0] as Record<string, unknown>;
  };

  const matches = (patterns: (string | RegExp)[], message: string) =>
    patterns.some((pattern) =>
      typeof pattern === "string"
        ? message.includes(pattern)
        : pattern.test(message),
    );

  it("ships a default ignoreErrors list", () => {
    expect(init().ignoreErrors).toBeInstanceOf(Array);
  });

  // Every one of these was an unresolved issue in the Sentry inbox, and
  // none of them is our code: a wallet extension, an iOS webview probing
  // for a Safari-only handler, and a Deno-based extension bootstrap.
  it.each([
    "i: Failed to connect to MetaMask",
    "TypeError: undefined is not an object (evaluating 'window.webkit.messageHandlers')",
    "Cannot read properties of undefined (reading 'toLowerCase')\n    at <obscura:bootstrap>:346:75",
  ])("drops third-party noise: %s", (message) => {
    const patterns = init().ignoreErrors as (string | RegExp)[];
    expect(matches(patterns, message)).toBe(true);
  });

  it("keeps real application errors", () => {
    const patterns = init().ignoreErrors as (string | RegExp)[];
    expect(
      matches(patterns, "TypeError: company.ticker is undefined"),
    ).toBe(false);
    expect(matches(patterns, "Failed to fetch fundamentals")).toBe(false);
  });

  it("lets a caller replace the defaults", () => {
    const options = init({ ignoreErrors: ["only-this"] });
    expect(options.ignoreErrors).toEqual(["only-this"]);
  });
});
