// @vitest-environment jsdom
import { describe, it, expect, beforeEach, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import {
  useMcpAnnouncement,
  MCP_ANNOUNCEMENT_DISMISSED_STORAGE_KEY,
} from "./useMcpAnnouncement";

function createLocalStorageStub() {
  let store: Record<string, string> = {};
  return {
    getItem: (key: string) => (key in store ? store[key] : null),
    setItem: (key: string, value: string) => {
      store[key] = value;
    },
    removeItem: (key: string) => {
      delete store[key];
    },
    clear: () => {
      store = {};
    },
  };
}

beforeEach(() => {
  vi.stubGlobal("localStorage", createLocalStorageStub());
});

describe("useMcpAnnouncement", () => {
  it("opens on page load when the announcement was never dismissed", () => {
    const { result } = renderHook(() => useMcpAnnouncement());

    expect(result.current.isOpen).toBe(true);
  });

  it("stays closed on page load when the announcement was dismissed before", () => {
    window.localStorage.setItem(MCP_ANNOUNCEMENT_DISMISSED_STORAGE_KEY, "true");

    const { result } = renderHook(() => useMcpAnnouncement());

    expect(result.current.isOpen).toBe(false);
  });

  it("close() hides the announcement and persists the dismissal", () => {
    const { result } = renderHook(() => useMcpAnnouncement());

    act(() => result.current.close());

    expect(result.current.isOpen).toBe(false);
    expect(
      window.localStorage.getItem(MCP_ANNOUNCEMENT_DISMISSED_STORAGE_KEY),
    ).toBe("true");
  });

  it("does not reopen on a later page load after being dismissed", () => {
    const firstPageLoad = renderHook(() => useMcpAnnouncement());
    act(() => firstPageLoad.result.current.close());
    firstPageLoad.unmount();

    const secondPageLoad = renderHook(() => useMcpAnnouncement());

    expect(secondPageLoad.result.current.isOpen).toBe(false);
  });

  it("open() shows the announcement again even after dismissal", () => {
    window.localStorage.setItem(MCP_ANNOUNCEMENT_DISMISSED_STORAGE_KEY, "true");

    const { result } = renderHook(() => useMcpAnnouncement());
    act(() => result.current.open());

    expect(result.current.isOpen).toBe(true);
  });
});
