"use client";

import { createContext, useContext, useEffect, useState } from "react";

const STORAGE_KEY = "sponda-left-nav-open";
const MOBILE_BREAKPOINT = 900;

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
  const [open, setOpenState] = useState(false);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored === "1") setOpenState(true);
    else if (stored === "0") setOpenState(false);
    else setOpenState(window.innerWidth >= MOBILE_BREAKPOINT);
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    if (typeof window === "undefined") return;
    const root = document.documentElement;
    root.style.setProperty("--left-nav-width", open ? "240px" : "0px");
    if (open) root.classList.add("left-nav-open");
    else root.classList.remove("left-nav-open");
  }, [open, hydrated]);

  function setOpen(next: boolean) {
    setOpenState(next);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(STORAGE_KEY, next ? "1" : "0");
    }
  }

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
