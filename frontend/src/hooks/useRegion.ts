import { useSyncExternalStore } from "react";
import { type Region, detectRegion } from "../utils/region";

/**
 * The visitor's region, inferred from their browser timezone.
 *
 * The server cannot know it, so it renders "brazil" and so does the hydration
 * pass; the detected value lands on the re-render immediately after. Spelled
 * with `useSyncExternalStore` rather than a mount effect because the timezone
 * does not change: there is nothing to subscribe to, only a snapshot that
 * differs between server and client.
 */

/** Nothing to subscribe to: a timezone does not change under a running tab. */
const subscribeToNothing = () => () => {};

/** Matches the server default so the first client paint agrees with the markup. */
const REGION_WHILE_SERVER_RENDERING: Region = "brazil";
const regionOnServer = () => REGION_WHILE_SERVER_RENDERING;

export function useRegion(): Region {
  // Safe as a snapshot: detectRegion returns one of a fixed set of strings, so
  // it compares by value and cannot loop the way a fresh object would.
  return useSyncExternalStore(subscribeToNothing, detectRegion, regionOnServer);
}
