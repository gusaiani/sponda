// @vitest-environment jsdom

import { describe, it, expect } from "vitest";
import { renderHook, act } from "@testing-library/react";
import type { ReactNode } from "react";
import {
  AssistantWindowProvider,
  useAssistantWindow,
  useSetAssistantWindow,
} from "./AssistantWindowContext";

function useWindowPair() {
  return { years: useAssistantWindow(), setYears: useSetAssistantWindow() };
}

describe("AssistantWindowContext", () => {
  it("shares the window one consumer sets with another", () => {
    const wrapper = ({ children }: { children: ReactNode }) => (
      <AssistantWindowProvider>{children}</AssistantWindowProvider>
    );
    const { result } = renderHook(useWindowPair, { wrapper });

    expect(result.current.years).toBeNull();
    act(() => result.current.setYears(5));
    expect(result.current.years).toBe(5);
  });

  it("returns null and a safe no-op outside a provider", () => {
    const { result } = renderHook(useWindowPair);

    expect(result.current.years).toBeNull();
    // Must not throw even with no provider above it.
    act(() => result.current.setYears(10));
    expect(result.current.years).toBeNull();
  });
});
