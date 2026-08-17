// @vitest-environment jsdom
import { describe, it, expect, afterEach, beforeEach, vi } from "vitest";
import { render, cleanup, act } from "@testing-library/react";
import { renderToString } from "react-dom/server";
import { useStoredState } from "./useStoredState";

// Same stub the other storage-backed tests in this repo use.
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
afterEach(cleanup);

const KEY = "test-key";

function Flag({ onRender }: { onRender?: (value: boolean) => void }) {
  const [value, setValue] = useStoredState(KEY, false, (raw) => raw === "1", (v) => (v ? "1" : "0"));
  onRender?.(value);
  return (
    <button onClick={() => setValue(!value)}>{value ? "on" : "off"}</button>
  );
}

describe("useStoredState", () => {
  it("uses the server value while server-rendering, whatever is in storage", () => {
    // The server has no localStorage. Rendering the stored value there would
    // produce markup the client cannot match.
    expect(renderToString(<Flag />)).toContain("off");
  });

  it("falls back to the server value when nothing is stored", () => {
    const { getByRole } = render(<Flag />);

    expect(getByRole("button").textContent).toBe("off");
  });

  it("reads what is already in storage", () => {
    window.localStorage.setItem(KEY, "1");

    const { getByRole } = render(<Flag />);

    expect(getByRole("button").textContent).toBe("on");
  });

  it("persists a change and reflects it", () => {
    const { getByRole } = render(<Flag />);

    act(() => getByRole("button").click());

    expect(getByRole("button").textContent).toBe("on");
    expect(window.localStorage.getItem(KEY)).toBe("1");
  });

  it("keeps two components on the same key in step", () => {
    // Same tab: without a shared subscription the second component would
    // keep rendering the old value until something else re-rendered it.
    const { getAllByRole } = render(
      <>
        <Flag />
        <Flag />
      </>,
    );
    const [first, second] = getAllByRole("button");

    act(() => first.click());

    expect(first.textContent).toBe("on");
    expect(second.textContent).toBe("on");
  });

  it("returns a stable snapshot for object values", () => {
    // useSyncExternalStore re-renders forever if getSnapshot returns a new
    // object each call, so parsed values have to be cached by raw string.
    window.localStorage.setItem(KEY, JSON.stringify({ a: 1 }));
    const seen: unknown[] = [];
    function ObjectReader() {
      const [value] = useStoredState<Record<string, number>>(
        KEY, {}, (raw) => (raw ? JSON.parse(raw) : {}), JSON.stringify,
      );
      seen.push(value);
      return null;
    }

    const { rerender } = render(<ObjectReader />);
    rerender(<ObjectReader />);
    rerender(<ObjectReader />);

    expect(seen.length).toBeGreaterThan(1);
    expect(new Set(seen).size).toBe(1);
  });

  it("falls back instead of throwing on malformed stored data", () => {
    window.localStorage.setItem(KEY, "{not json");
    function ObjectReader() {
      const [value] = useStoredState<Record<string, number>>(
        KEY, { fallback: 1 }, (raw) => (raw ? JSON.parse(raw) : {}), JSON.stringify,
      );
      return <span>{Object.keys(value).join(",")}</span>;
    }

    const { container } = render(<ObjectReader />);

    expect(container.textContent).toBe("fallback");
  });
});
