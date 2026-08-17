// @vitest-environment jsdom
import { describe, it, expect, beforeEach, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import {
  useMcpAnnouncement,
  MCP_ANNOUNCEMENT_DISMISSED_STORAGE_KEY,
  MCP_ANNOUNCEMENT_QUERY_PARAM,
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

function visit(url: string) {
  window.history.replaceState({}, "", url);
}

beforeEach(() => {
  vi.stubGlobal("localStorage", createLocalStorageStub());
  visit("/");
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

/**
 * The announcement email links here to show the modal. Without the parameter
 * the link is dead for exactly the people most likely to click it: anyone who
 * already visited the site and dismissed the modal once.
 */
describe("useMcpAnnouncement, opened by the URL", () => {
  it(`opens when ?${MCP_ANNOUNCEMENT_QUERY_PARAM} is present and it was dismissed before`, () => {
    window.localStorage.setItem(MCP_ANNOUNCEMENT_DISMISSED_STORAGE_KEY, "true");
    visit(`/en?${MCP_ANNOUNCEMENT_QUERY_PARAM}=1`);

    const { result } = renderHook(() => useMcpAnnouncement());

    expect(result.current.isOpen).toBe(true);
  });

  it("opens on a bare parameter with no value", () => {
    window.localStorage.setItem(MCP_ANNOUNCEMENT_DISMISSED_STORAGE_KEY, "true");
    visit(`/en?${MCP_ANNOUNCEMENT_QUERY_PARAM}`);

    const { result } = renderHook(() => useMcpAnnouncement());

    expect(result.current.isOpen).toBe(true);
  });

  it("stays closed when some other parameter is present", () => {
    window.localStorage.setItem(MCP_ANNOUNCEMENT_DISMISSED_STORAGE_KEY, "true");
    visit("/en?utm_source=email");

    const { result } = renderHook(() => useMcpAnnouncement());

    expect(result.current.isOpen).toBe(false);
  });

  it("can still be closed while the parameter is in the URL", () => {
    // The parameter must not outrank the close button, or the modal traps
    // the visitor until they edit the address bar.
    visit(`/en?${MCP_ANNOUNCEMENT_QUERY_PARAM}=1`);
    const { result } = renderHook(() => useMcpAnnouncement());

    act(() => result.current.close());

    expect(result.current.isOpen).toBe(false);
  });

  it("persists the dismissal when closed from a link visit", () => {
    visit(`/en?${MCP_ANNOUNCEMENT_QUERY_PARAM}=1`);
    const { result } = renderHook(() => useMcpAnnouncement());

    act(() => result.current.close());

    expect(
      window.localStorage.getItem(MCP_ANNOUNCEMENT_DISMISSED_STORAGE_KEY),
    ).toBe("true");
  });
});
