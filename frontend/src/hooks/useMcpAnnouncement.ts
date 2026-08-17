"use client";

import { useCallback, useState, useSyncExternalStore } from "react";
import { useStoredState } from "./useStoredState";

export const MCP_ANNOUNCEMENT_DISMISSED_STORAGE_KEY =
  "sponda-mcp-announcement-dismissed";

/**
 * Link to `/<locale>?mcp=1` to force the modal open. The announcement email
 * uses it: without the parameter the call-to-action is dead for exactly the
 * readers most likely to click it, since anyone who already visited the site
 * and closed the modal once would land on an unchanged homepage.
 */
export const MCP_ANNOUNCEMENT_QUERY_PARAM = "mcp";

/**
 * The server has no localStorage and must not render the modal, so it renders
 * as though the visitor had already dismissed it.
 */
const DISMISSED_WHILE_SERVER_RENDERING = true;

const parseDismissed = (raw: string | null): boolean => raw === "true";
const serializeDismissed = (dismissed: boolean): string => String(dismissed);

/**
 * What this view says about the modal, on top of the stored dismissal. The
 * header button and the close button both need to outrank everything else for
 * the rest of the visit, in opposite directions, and a single value says that
 * more clearly than two booleans that must never both be true.
 */
type ViewOverride = "none" | "opened" | "closed";

/** The query string never changes without a navigation, so nothing to watch. */
const subscribeToNothing = () => () => {};
const searchOnClient = () => window.location.search;
const noSearchOnServer = () => "";

/**
 * True when the current URL asks for the modal.
 *
 * Read through `useSyncExternalStore` rather than an effect, for the same
 * reason `useStoredState` is: the server snapshot is the empty query string,
 * so server markup and first client paint agree without a second render pass.
 * `useSearchParams` would also work but opts the whole route into client-side
 * rendering, which is a heavy price for one optional parameter.
 */
function useModalRequestedByUrl(): boolean {
  const search = useSyncExternalStore(
    subscribeToNothing,
    searchOnClient,
    noSearchOnServer,
  );
  return new URLSearchParams(search).has(MCP_ANNOUNCEMENT_QUERY_PARAM);
}

/**
 * Controls the MCP announcement modal. It opens automatically on page load
 * until the visitor dismisses it once (persisted in localStorage, so it works
 * for logged-in and logged-out visitors alike), can always be reopened from
 * the "MCP" header button, and opens on demand for a link carrying
 * `?mcp=1`.
 */
export function useMcpAnnouncement() {
  const [dismissed, setDismissed] = useStoredState(
    MCP_ANNOUNCEMENT_DISMISSED_STORAGE_KEY,
    DISMISSED_WHILE_SERVER_RENDERING,
    parseDismissed,
    serializeDismissed,
  );
  const requestedByUrl = useModalRequestedByUrl();

  // Reopening from the header button overrides a past dismissal for this view
  // only. It deliberately does not clear the stored flag: closing again should
  // not make the modal come back on the next page load.
  const [override, setOverride] = useState<ViewOverride>("none");

  const open = useCallback(() => setOverride("opened"), []);

  // "closed" has to be recorded, not merely stored: on a `?mcp=1` visit the
  // URL keeps asking for the modal, so without this the close button would do
  // nothing and the visitor would be trapped until they edited the address.
  const close = useCallback(() => {
    setDismissed(true);
    setOverride("closed");
  }, [setDismissed]);

  const isOpen =
    override === "none" ? requestedByUrl || !dismissed : override === "opened";

  return { isOpen, open, close } as const;
}
