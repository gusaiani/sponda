// @vitest-environment jsdom
import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import {
  rememberPostLoginReturn,
  consumePostLoginReturnPath,
  consumePendingAuthAction,
  PENDING_ACTION_LIFETIME_MILLISECONDS,
} from "./postLoginReturn";

beforeEach(() => {
  window.sessionStorage.clear();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("consumePostLoginReturnPath", () => {
  it("returns the remembered same-origin path once", () => {
    rememberPostLoginReturn("/pt/VALE3?tab=charts");

    expect(consumePostLoginReturnPath()).toBe("/pt/VALE3?tab=charts");
    expect(consumePostLoginReturnPath()).toBeNull();
  });

  it("returns null when nothing was remembered", () => {
    expect(consumePostLoginReturnPath()).toBeNull();
  });

  it.each([
    "//evil.example.com/pt",
    "/\\evil.example.com",
    "https://evil.example.com/pt",
    "javascript:alert(1)",
    "pt/VALE3",
  ])("rejects the unsafe path %s", (unsafePath) => {
    window.sessionStorage.setItem(
      "sponda.postLoginReturn",
      JSON.stringify({ path: unsafePath, savedAt: Date.now() }),
    );

    expect(consumePostLoginReturnPath()).toBeNull();
  });

  it("ignores malformed storage content", () => {
    window.sessionStorage.setItem("sponda.postLoginReturn", "{not json");

    expect(consumePostLoginReturnPath()).toBeNull();
  });
});

describe("consumePendingAuthAction", () => {
  it("returns true once for the matching action and ticker", () => {
    rememberPostLoginReturn("/pt/VALE3", { kind: "mark-visited", ticker: "vale3" });

    expect(consumePendingAuthAction({ kind: "mark-visited", ticker: "VALE3" })).toBe(true);
    expect(consumePendingAuthAction({ kind: "mark-visited", ticker: "VALE3" })).toBe(false);
  });

  it("does not consume an action meant for another ticker", () => {
    rememberPostLoginReturn("/pt/VALE3", { kind: "mark-visited", ticker: "VALE3" });

    expect(consumePendingAuthAction({ kind: "mark-visited", ticker: "PETR4" })).toBe(false);
    expect(consumePendingAuthAction({ kind: "mark-visited", ticker: "VALE3" })).toBe(true);
  });

  it("keeps the pending action after the return path is consumed", () => {
    rememberPostLoginReturn("/pt/VALE3", { kind: "mark-visited", ticker: "VALE3" });

    consumePostLoginReturnPath();

    expect(consumePendingAuthAction({ kind: "mark-visited", ticker: "VALE3" })).toBe(true);
  });

  it("expires a stale pending action", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-11-18T12:00:00Z"));
    rememberPostLoginReturn("/pt/VALE3", { kind: "mark-visited", ticker: "VALE3" });

    vi.setSystemTime(Date.now() + PENDING_ACTION_LIFETIME_MILLISECONDS + 1);

    expect(consumePendingAuthAction({ kind: "mark-visited", ticker: "VALE3" })).toBe(false);
  });

  it("clears a previous pending action when a new return is remembered without one", () => {
    rememberPostLoginReturn("/pt/VALE3", { kind: "mark-visited", ticker: "VALE3" });
    rememberPostLoginReturn("/pt/PETR4");

    expect(consumePendingAuthAction({ kind: "mark-visited", ticker: "VALE3" })).toBe(false);
  });
});
