"use client";

import { useSyncExternalStore } from "react";

/**
 * True once the component is running in the browser, false while the server
 * renders it.
 *
 * Components that portal into `document.body`, or otherwise touch APIs that
 * only exist client-side, need to render nothing on the server and the real
 * thing after hydration. The usual way to spell that is a `mounted` flag set
 * from an empty effect, which costs an extra render pass and trips
 * `react-hooks/set-state-in-effect`.
 *
 * `useSyncExternalStore` says the same thing directly: the server snapshot is
 * false, the client snapshot is true, and React handles the transition. No
 * state, no effect.
 */

/** Nothing ever changes, so the subscription is a no-op that never fires. */
const subscribeToNothing = () => () => {};
const hydrated = () => true;
const notHydratedOnServer = () => false;

export function useIsHydrated(): boolean {
  return useSyncExternalStore(subscribeToNothing, hydrated, notHydratedOnServer);
}
