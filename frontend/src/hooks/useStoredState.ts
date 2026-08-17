"use client";

import { useCallback, useSyncExternalStore } from "react";

/**
 * State backed by localStorage, readable during SSR without a hydration
 * mismatch and without an effect.
 *
 * The pattern this replaces is: render a default, then read localStorage in a
 * mount effect and setState. That works, but it costs an extra render pass,
 * it trips `react-hooks/set-state-in-effect`, and two components sharing a key
 * drift apart because neither hears about the other's writes.
 *
 * `useSyncExternalStore` states the same intent directly. The server snapshot
 * is the caller's default, so server markup and first client paint agree; the
 * client snapshot is whatever is stored; and a shared subscription keeps every
 * consumer of a key in step.
 *
 * Deliberately same-tab only: it does not listen for the `storage` event. That
 * would add cross-tab syncing, which is a behaviour change none of the current
 * callers asked for. Adding it later is one listener.
 *
 * Two constraints fall out of the snapshot cache, and both bite silently:
 *
 * 1. **One `parse` meaning per key.** The cache holds a single entry per key,
 *    so two components reading the same key into different shapes would hand
 *    each other the wrong one. `parse` itself may be an inline arrow — the
 *    cache is keyed by the raw string, not by function identity, which is
 *    exactly what keeps the snapshot stable when it is.
 * 2. **`serverValue` must be referentially stable.** Pass a module-level
 *    constant, not an inline `{}` or `[]`. React reads the server snapshot
 *    during hydration and a fresh object every render defeats it.
 */

type Listener = () => void;

const listenersByKey = new Map<string, Set<Listener>>();

/**
 * `getSnapshot` must return a referentially stable value or React re-renders
 * forever, so parsed values are cached against the raw string they came from.
 */
const snapshotCache = new Map<string, { raw: string | null; value: unknown }>();

function notify(key: string): void {
  listenersByKey.get(key)?.forEach((listener) => listener());
}

function readRaw(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    // Safari in private mode, and any browser with storage disabled.
    return null;
  }
}

export function useStoredState<T>(
  key: string,
  serverValue: T,
  parse: (raw: string | null) => T,
  serialize: (value: T) => string,
): [T, (next: T) => void] {
  const subscribe = useCallback((listener: Listener) => {
    const listeners = listenersByKey.get(key) ?? new Set<Listener>();
    listeners.add(listener);
    listenersByKey.set(key, listeners);
    return () => {
      listeners.delete(listener);
      if (listeners.size === 0) listenersByKey.delete(key);
    };
  }, [key]);

  const getSnapshot = useCallback((): T => {
    const raw = readRaw(key);
    const cached = snapshotCache.get(key);
    if (cached && cached.raw === raw) return cached.value as T;

    let value: T;
    try {
      value = parse(raw);
    } catch {
      // Malformed stored data must not take the page down with it.
      value = serverValue;
    }
    snapshotCache.set(key, { raw, value });
    return value;
  }, [key, parse, serverValue]);

  const getServerSnapshot = useCallback(() => serverValue, [serverValue]);

  const value = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);

  const setValue = useCallback((next: T) => {
    try {
      window.localStorage.setItem(key, serialize(next));
    } catch {
      // Storage full or unavailable: keep the in-memory value in step anyway,
      // so the UI still responds even though the choice will not survive.
    }
    snapshotCache.delete(key);
    notify(key);
  }, [key, serialize]);

  return [value, setValue];
}
