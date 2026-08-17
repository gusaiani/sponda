"use client";

import { useCallback, useState } from "react";
import { useStoredState } from "./useStoredState";

export const MCP_ANNOUNCEMENT_DISMISSED_STORAGE_KEY =
  "sponda-mcp-announcement-dismissed";

/**
 * The server has no localStorage and must not render the modal, so it renders
 * as though the visitor had already dismissed it.
 */
const DISMISSED_WHILE_SERVER_RENDERING = true;

const parseDismissed = (raw: string | null): boolean => raw === "true";
const serializeDismissed = (dismissed: boolean): string => String(dismissed);

/**
 * Controls the MCP announcement modal. It opens automatically on page load
 * until the visitor dismisses it once (persisted in localStorage, so it works
 * for logged-in and logged-out visitors alike), and can always be reopened
 * from the "MCP" header button.
 */
export function useMcpAnnouncement() {
  const [dismissed, setDismissed] = useStoredState(
    MCP_ANNOUNCEMENT_DISMISSED_STORAGE_KEY,
    DISMISSED_WHILE_SERVER_RENDERING,
    parseDismissed,
    serializeDismissed,
  );

  // Reopening from the header button overrides a past dismissal for this view
  // only. It deliberately does not clear the stored flag: closing again should
  // not make the modal come back on the next page load.
  const [reopened, setReopened] = useState(false);

  const open = useCallback(() => setReopened(true), []);

  const close = useCallback(() => {
    setDismissed(true);
    setReopened(false);
  }, [setDismissed]);

  return { isOpen: reopened || !dismissed, open, close } as const;
}
