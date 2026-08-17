// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, cleanup, act } from "@testing-library/react";
import { LeftNavProvider, useLeftNav } from "./LeftNavContext";

/**
 * Characterisation tests for the left nav, written before moving its
 * localStorage read out of an effect. The settled state has to be identical
 * before and after.
 */

const STORAGE_KEY = "sponda-left-nav-open";

function createLocalStorageStub() {
  let store: Record<string, string> = {};
  return {
    getItem: (key: string) => (key in store ? store[key] : null),
    setItem: (key: string, value: string) => { store[key] = value; },
    removeItem: (key: string) => { delete store[key]; },
    clear: () => { store = {}; },
  };
}

function setViewportWidth(width: number) {
  Object.defineProperty(window, "innerWidth", { value: width, configurable: true });
}

beforeEach(() => {
  vi.stubGlobal("localStorage", createLocalStorageStub());
  document.documentElement.style.removeProperty("--left-nav-width");
  document.documentElement.classList.remove("left-nav-open");
});

afterEach(cleanup);

function renderNav() {
  let api!: ReturnType<typeof useLeftNav>;
  function Reader() {
    api = useLeftNav();
    return <span>{api.open ? "open" : "closed"}</span>;
  }
  const utils = render(
    <LeftNavProvider>
      <Reader />
    </LeftNavProvider>,
  );
  return { ...utils, api: () => api };
}

describe("LeftNavProvider", () => {
  it("opens by default on a desktop-width viewport", () => {
    setViewportWidth(1200);

    const { container } = renderNav();

    expect(container.textContent).toBe("open");
  });

  it("stays closed by default on a narrow viewport", () => {
    setViewportWidth(500);

    const { container } = renderNav();

    expect(container.textContent).toBe("closed");
  });

  it("honours a stored preference over the viewport default", () => {
    setViewportWidth(1200);
    window.localStorage.setItem(STORAGE_KEY, "0");

    const { container } = renderNav();

    expect(container.textContent).toBe("closed");
  });

  it("honours a stored open preference on a narrow viewport", () => {
    setViewportWidth(500);
    window.localStorage.setItem(STORAGE_KEY, "1");

    const { container } = renderNav();

    expect(container.textContent).toBe("open");
  });

  it("persists a toggle", () => {
    setViewportWidth(500);
    const { container, api } = renderNav();

    act(() => api().toggle());

    expect(container.textContent).toBe("open");
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe("1");
  });

  it("mirrors the state onto the document root for CSS", () => {
    setViewportWidth(1200);

    renderNav();

    expect(document.documentElement.style.getPropertyValue("--left-nav-width")).toBe("240px");
    expect(document.documentElement.classList.contains("left-nav-open")).toBe(true);
  });

  it("clears the root class when closed", () => {
    setViewportWidth(1200);
    const { api } = renderNav();

    act(() => api().setOpen(false));

    expect(document.documentElement.style.getPropertyValue("--left-nav-width")).toBe("0px");
    expect(document.documentElement.classList.contains("left-nav-open")).toBe(false);
  });
});
