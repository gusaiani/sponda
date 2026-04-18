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
    expect(options.tracesSampleRate).toBe(1.0);
    expect(options.replaysSessionSampleRate).toBe(0.1);
    expect(options.replaysOnErrorSampleRate).toBe(1.0);
  });
});
