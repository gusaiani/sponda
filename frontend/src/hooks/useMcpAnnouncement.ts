"use client";

import { useCallback, useEffect, useState } from "react";

export const MCP_ANNOUNCEMENT_DISMISSED_STORAGE_KEY =
  "sponda-mcp-announcement-dismissed";

function isMcpAnnouncementDismissed(): boolean {
  if (typeof window === "undefined") return true;
  return (
    window.localStorage.getItem(MCP_ANNOUNCEMENT_DISMISSED_STORAGE_KEY) ===
    "true"
  );
}

/**
 * Controls the MCP announcement modal. It opens automatically on page load
 * until the visitor dismisses it once (persisted in localStorage, so it works
 * for logged-in and logged-out visitors alike), and can always be reopened
 * from the "MCP" header button.
 */
export function useMcpAnnouncement() {
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    if (!isMcpAnnouncementDismissed()) setIsOpen(true);
  }, []);

  const open = useCallback(() => setIsOpen(true), []);

  const close = useCallback(() => {
    window.localStorage.setItem(MCP_ANNOUNCEMENT_DISMISSED_STORAGE_KEY, "true");
    setIsOpen(false);
  }, []);

  return { isOpen, open, close } as const;
}
