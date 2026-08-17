// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, cleanup } from "@testing-library/react";
import { renderToString } from "react-dom/server";
import { useRegion } from "./useRegion";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function Probe() {
  return <span>{useRegion()}</span>;
}

function pretendTimezone(timeZone: string) {
  vi.spyOn(Intl, "DateTimeFormat").mockReturnValue({
    resolvedOptions: () => ({ timeZone }),
  } as unknown as Intl.DateTimeFormat);
}

describe("useRegion", () => {
  it("says brazil while server-rendering, whatever the timezone", () => {
    // The server has no idea where the visitor is; rendering a guess there
    // would mismatch on hydration.
    pretendTimezone("Europe/Berlin");

    expect(renderToString(<Probe />)).toContain("brazil");
  });

  it("detects a European visitor in the browser", () => {
    pretendTimezone("Europe/Berlin");

    const { container } = render(<Probe />);

    expect(container.textContent).toBe("europe");
  });

  it("detects a Brazilian visitor", () => {
    pretendTimezone("America/Sao_Paulo");

    const { container } = render(<Probe />);

    expect(container.textContent).toBe("brazil");
  });

  it("falls back to us for anything unrecognised", () => {
    pretendTimezone("America/New_York");

    const { container } = render(<Probe />);

    expect(container.textContent).toBe("us");
  });
});
