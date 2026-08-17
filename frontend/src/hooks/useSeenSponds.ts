"use client";

import { useCallback } from "react";
import { useStoredState } from "./useStoredState";

const STORAGE_KEY = "sponda-social-seen-sponds";
const SEEN_TTL_MS = 7 * 24 * 60 * 60 * 1000; // prune entries older than 7d
const FORTY_EIGHT_HOURS_MS = 48 * 60 * 60 * 1000;

type SeenMap = Record<string, number>;

/** Module-level so the server snapshot keeps a stable identity. */
const NOTHING_SEEN: SeenMap = {};

/**
 * Pure in the raw string. Pruning used to happen here, on load, but reading
 * the clock inside a parse makes it impure and `useStoredState` caches parsed
 * values against the raw string. Pruning moved to the write path below, which
 * bounds the stored size just as well: every markSeen rewrites the map.
 */
function parseSeen(raw: string | null): SeenMap {
  if (!raw) return NOTHING_SEEN;
  const parsed = JSON.parse(raw) as SeenMap;
  return parsed && typeof parsed === "object" ? parsed : NOTHING_SEEN;
}

const serializeSeen = (map: SeenMap): string => JSON.stringify(map);

function withoutExpired(map: SeenMap, now: number): SeenMap {
  const kept: SeenMap = {};
  for (const [id, timestamp] of Object.entries(map)) {
    if (now - timestamp < SEEN_TTL_MS) kept[id] = timestamp;
  }
  return kept;
}

/**
 * Track which Sponds the viewer has "seen" so the collapsed-rail badge
 * only counts genuinely new content.
 *
 * A Spond is considered seen if EITHER:
 *   - it is older than 48 hours (auto-aged out), OR
 *   - the user has explicitly observed it — i.e. it scrolled into the
 *     viewport (the IntersectionObserver in SpondCard calls markSeen).
 *
 * Persistence uses localStorage. Entries older than 7 days are dropped
 * whenever the map is written — long enough to debounce the "seen" rule
 * across sessions, short enough to keep the payload small.
 */
export function useSeenSponds() {
  const [seen, setSeen] = useStoredState<SeenMap>(
    STORAGE_KEY, NOTHING_SEEN, parseSeen, serializeSeen,
  );

  const markSeen = useCallback((spondId: string) => {
    if (seen[spondId]) return;
    const now = Date.now();
    setSeen({ ...withoutExpired(seen, now), [spondId]: now });
  }, [seen, setSeen]);

  const isSeen = useCallback(
    (spondId: string, createdAt: string) => {
      if (seen[spondId]) return true;
      const age = Date.now() - new Date(createdAt).getTime();
      return age > FORTY_EIGHT_HOURS_MS;
    },
    [seen],
  );

  return { markSeen, isSeen };
}
