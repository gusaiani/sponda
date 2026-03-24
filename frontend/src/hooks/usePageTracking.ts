import { useEffect, useRef } from "react";
import { usePathname } from "next/navigation";

/**
 * Tracks page views by POSTing to the backend on every route change.
 */
export function usePageTracking() {
  const pathname = usePathname();
  const lastTrackedPath = useRef<string>("");

  useEffect(() => {
    const path = pathname;

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
  }, [pathname]);
}
