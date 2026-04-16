// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook } from "@testing-library/react";
import { useRef } from "react";
import { useInfiniteScrollTrigger } from "./useInfiniteScrollTrigger";

/**
 * Minimal IntersectionObserver stub: records observe/disconnect calls and
 * exposes the callback so tests can simulate visibility changes.
 */
interface ObserverInstance {
  callback: IntersectionObserverCallback;
  observed: Element[];
  disconnected: boolean;
}

let observerInstances: ObserverInstance[] = [];

class FakeIntersectionObserver {
  callback: IntersectionObserverCallback;
  observed: Element[] = [];
  disconnected = false;

  constructor(callback: IntersectionObserverCallback) {
    this.callback = callback;
    observerInstances.push(this);
  }

  observe(target: Element) {
    this.observed.push(target);
  }

  unobserve() {
    // no-op — we rely on disconnect in cleanup
  }

  disconnect() {
    this.disconnected = true;
  }

  takeRecords(): IntersectionObserverEntry[] {
    return [];
  }

  root = null;
  rootMargin = "";
  thresholds: ReadonlyArray<number> = [];
}

beforeEach(() => {
  observerInstances = [];
  vi.stubGlobal("IntersectionObserver", FakeIntersectionObserver);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function latestObserver(): ObserverInstance {
  return observerInstances[observerInstances.length - 1];
}

function renderTrigger(options: {
  enabled: boolean;
  onVisible: () => void;
  element?: Element | null;
}) {
  return renderHook(() => {
    const ref = useRef<HTMLDivElement | null>(
      (options.element ?? document.createElement("div")) as HTMLDivElement,
    );
    useInfiniteScrollTrigger({
      ref,
      enabled: options.enabled,
      onVisible: options.onVisible,
    });
    return ref;
  });
}

describe("useInfiniteScrollTrigger", () => {
  it("observes the ref element when enabled", () => {
    const onVisible = vi.fn();
    renderTrigger({ enabled: true, onVisible });

    expect(observerInstances).toHaveLength(1);
    expect(latestObserver().observed).toHaveLength(1);
  });

  it("does not create an observer while disabled", () => {
    const onVisible = vi.fn();
    renderTrigger({ enabled: false, onVisible });

    expect(observerInstances).toHaveLength(0);
  });

  it("invokes onVisible when the sentinel becomes intersecting", () => {
    const onVisible = vi.fn();
    renderTrigger({ enabled: true, onVisible });

    const observer = latestObserver();
    observer.callback(
      [{ isIntersecting: true } as IntersectionObserverEntry],
      observer as unknown as IntersectionObserver,
    );

    expect(onVisible).toHaveBeenCalledTimes(1);
  });

  it("does not invoke onVisible when the sentinel is not intersecting", () => {
    const onVisible = vi.fn();
    renderTrigger({ enabled: true, onVisible });

    const observer = latestObserver();
    observer.callback(
      [{ isIntersecting: false } as IntersectionObserverEntry],
      observer as unknown as IntersectionObserver,
    );

    expect(onVisible).not.toHaveBeenCalled();
  });

  it("disconnects the observer when the hook unmounts", () => {
    const onVisible = vi.fn();
    const { unmount } = renderTrigger({ enabled: true, onVisible });

    const observer = latestObserver();
    unmount();
    expect(observer.disconnected).toBe(true);
  });
});
