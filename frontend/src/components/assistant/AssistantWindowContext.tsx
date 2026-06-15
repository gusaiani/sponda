"use client";

import {
  createContext,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

interface AssistantWindowValue {
  years: number | null;
  setYears: (years: number | null) => void;
}

const AssistantWindowContext = createContext<AssistantWindowValue | null>(null);

// Stable no-op so consumers outside a provider (e.g. isolated tests) get a
// referentially-stable setter safe to use in an effect dependency list.
const NOOP = () => {};

/**
 * Shares the company page's PRAZO window (the year slider) with the floating
 * AssistantBar, which lives in the layout shell — a sibling of the page, so a
 * prop can't reach it. The page pushes its window up; the bar reads it and
 * sends it with each question, so the assistant reasons over the exact numbers
 * on screen rather than the backend's all-history default.
 */
export function AssistantWindowProvider({ children }: { children: ReactNode }) {
  const [years, setYears] = useState<number | null>(null);
  const value = useMemo(() => ({ years, setYears }), [years]);
  return (
    <AssistantWindowContext.Provider value={value}>
      {children}
    </AssistantWindowContext.Provider>
  );
}

/** Read the current PRAZO window. null = no window reported yet / outside a
 * provider; the backend then falls back to its all-history default. */
export function useAssistantWindow(): number | null {
  return useContext(AssistantWindowContext)?.years ?? null;
}

/** Push the current PRAZO window up to the AssistantBar. No-op outside a
 * provider. */
export function useSetAssistantWindow(): (years: number | null) => void {
  return useContext(AssistantWindowContext)?.setYears ?? NOOP;
}
