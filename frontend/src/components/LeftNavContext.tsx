"use client";

import { createContext, useContext, useEffect } from "react";
import { useIsHydrated } from "../hooks/useIsHydrated";
import { useStoredState } from "../hooks/useStoredState";

const STORAGE_KEY = "sponda-left-nav-open";
const MOBILE_BREAKPOINT = 900;

/** No stored preference yet: the viewport decides. */
const NO_PREFERENCE = null;

/**
 * Pure in the raw string, deliberately: `useStoredState` caches parsed values
 * against it, so a parse that also read the viewport would hand out a stale
 * answer after a resize. The viewport default is resolved in the provider,
 * after hydration, where it belongs.
 */
function parseStoredPreference(raw: string | null): boolean | null {
  if (raw === "1") return true;
  if (raw === "0") return false;
  return NO_PREFERENCE;
}

// Widened to match the stored type. Callers only ever set a real boolean;
// null would mean "no preference", which is the absence of a stored value.
const serializeOpen = (open: boolean | null): string => (open ? "1" : "0");

interface LeftNavContextValue {
  open: boolean;
  toggle: () => void;
  setOpen: (next: boolean) => void;
}

const LeftNavContext = createContext<LeftNavContextValue | null>(null);

/**
 * Provides shared state for the YouTube-style left navigation: is it
 * open (240px expanded) or closed (hidden / 0px)? Default depends on
 * viewport — desktop opens, mobile stays closed.
 *
 * The state is also written as a CSS variable on the document root so
 * any layout helper can read it without subscribing to React.
 */
export function LeftNavProvider({ children }: { children: React.ReactNode }) {
  const [storedPreference, setStoredPreference] = useStoredState<boolean | null>(
    STORAGE_KEY,
    NO_PREFERENCE,
    parseStoredPreference,
    serializeOpen,
  );
  // The server cannot measure a viewport, so it renders closed and so does the
  // hydration pass; the real default lands on the re-render straight after.
  const isHydrated = useIsHydrated();
  const open = storedPreference ?? (isHydrated && window.innerWidth >= MOBILE_BREAKPOINT);
  const setOpen = setStoredPreference;

  // Mirrored onto the document root so layout helpers can read the state
  // straight from CSS without subscribing to React.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const root = document.documentElement;
    root.style.setProperty("--left-nav-width", open ? "240px" : "0px");
    if (open) root.classList.add("left-nav-open");
    else root.classList.remove("left-nav-open");
  }, [open]);

  return (
    <LeftNavContext.Provider value={{ open, toggle: () => setOpen(!open), setOpen }}>
      {children}
    </LeftNavContext.Provider>
  );
}

export function useLeftNav(): LeftNavContextValue {
  const value = useContext(LeftNavContext);
  if (!value) {
    // Allow non-providered consumers (e.g. unit tests) to render without
    // crashing — they just see a "closed" nav and a noop toggle.
    return { open: false, toggle: () => {}, setOpen: () => {} };
  }
  return value;
}
