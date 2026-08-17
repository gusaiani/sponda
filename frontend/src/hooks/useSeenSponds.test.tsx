// @vitest-environment jsdom
import { describe, it, expect, beforeEach, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useSeenSponds } from "./useSeenSponds";

/**
 * Characterisation tests written before moving the localStorage read out of
 * an effect. Behaviour has to be identical before and after.
 */

const STORAGE_KEY = "sponda-social-seen-sponds";
const DAY_MS = 24 * 60 * 60 * 1000;

function createLocalStorageStub() {
  let store: Record<string, string> = {};
  return {
    getItem: (key: string) => (key in store ? store[key] : null),
    setItem: (key: string, value: string) => { store[key] = value; },
    removeItem: (key: string) => { delete store[key]; },
    clear: () => { store = {}; },
  };
}

beforeEach(() => {
  vi.stubGlobal("localStorage", createLocalStorageStub());
});

function isoAgo(ms: number) {
  return new Date(Date.now() - ms).toISOString();
}

describe("useSeenSponds", () => {
  it("treats a fresh spond nobody has looked at as unseen", () => {
    const { result } = renderHook(() => useSeenSponds());

    expect(result.current.isSeen("s1", isoAgo(60 * 1000))).toBe(false);
  });

  it("treats anything older than 48 hours as seen", () => {
    const { result } = renderHook(() => useSeenSponds());

    expect(result.current.isSeen("s1", isoAgo(3 * DAY_MS))).toBe(true);
  });

  it("marks a spond seen and persists it", () => {
    const { result } = renderHook(() => useSeenSponds());

    act(() => result.current.markSeen("s1"));

    expect(result.current.isSeen("s1", isoAgo(60 * 1000))).toBe(true);
    const stored = JSON.parse(window.localStorage.getItem(STORAGE_KEY) as string);
    expect(Object.keys(stored)).toContain("s1");
  });

  it("picks up sponds marked seen in an earlier session", () => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ s1: Date.now() }));

    const { result } = renderHook(() => useSeenSponds());

    expect(result.current.isSeen("s1", isoAgo(60 * 1000))).toBe(true);
  });

  it("drops entries older than the 7 day retention window", () => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({
      ancient: Date.now() - 8 * DAY_MS,
      recent: Date.now(),
    }));

    const { result } = renderHook(() => useSeenSponds());
    act(() => result.current.markSeen("s2"));

    const stored = JSON.parse(window.localStorage.getItem(STORAGE_KEY) as string);
    expect(Object.keys(stored).sort()).toEqual(["recent", "s2"]);
  });

  it("survives malformed stored data", () => {
    window.localStorage.setItem(STORAGE_KEY, "{not json");

    const { result } = renderHook(() => useSeenSponds());

    expect(result.current.isSeen("s1", isoAgo(60 * 1000))).toBe(false);
  });
});
