// @vitest-environment jsdom
import { describe, it, expect, afterEach } from "vitest";
import { render, cleanup } from "@testing-library/react";
import { renderToString } from "react-dom/server";
import { useIsHydrated } from "./useIsHydrated";

afterEach(cleanup);

function Probe() {
  return <span data-testid="probe">{useIsHydrated() ? "client" : "server"}</span>;
}

describe("useIsHydrated", () => {
  it("is false while server-rendering", () => {
    // The whole point: markup produced on the server must not include
    // anything that only exists in the browser, or hydration mismatches.
    expect(renderToString(<Probe />)).toContain("server");
  });

  it("is true in the browser", () => {
    const { getByTestId } = render(<Probe />);

    expect(getByTestId("probe").textContent).toBe("client");
  });

  it("does not change identity between renders once hydrated", () => {
    // useSyncExternalStore must return a stable snapshot or React loops.
    const seen: boolean[] = [];
    function Recorder() {
      seen.push(useIsHydrated());
      return null;
    }
    const { rerender } = render(<Recorder />);
    rerender(<Recorder />);
    rerender(<Recorder />);

    expect(seen.every((value) => value === true)).toBe(true);
  });
});
