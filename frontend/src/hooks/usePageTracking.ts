import { useEffect, useRef } from "react";
import { useLocation } from "@tanstack/react-router";

/**
 * Tracks page views by POSTing to the backend on every route change.
 * Works in both dev (Vite proxy) and production (Django serves everything).
 */
export function usePageTracking() {
  const location = useLocation();
  const lastTrackedPath = useRef<string>("");

  useEffect(() => {
    const path = location.pathname;

    // Skip admin pages and duplicates
    if (path.startsWith("/admin")) return;
    if (path === lastTrackedPath.current) return;
    lastTrackedPath.current = path;

    // Fire and forget — don't block rendering
    fetch("/api/auth/track/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ path }),
    }).catch(() => {
      // Silently ignore tracking failures
    });
  }, [location.pathname]);
}
