"use client";

import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "sponda-social-seen-sponds";
const SEEN_TTL_MS = 7 * 24 * 60 * 60 * 1000; // prune entries older than 7d
const FORTY_EIGHT_HOURS_MS = 48 * 60 * 60 * 1000;

type SeenMap = Record<string, number>;

function load(): SeenMap {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as SeenMap;
    const now = Date.now();
    // Prune entries older than the TTL so the map doesn't grow forever.
    const filtered: SeenMap = {};
    for (const [id, ts] of Object.entries(parsed)) {
      if (now - ts < SEEN_TTL_MS) filtered[id] = ts;
    }
    return filtered;
  } catch {
    return {};
  }
}

function save(map: SeenMap) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(map));
  } catch {
    /* quota / private mode — silent fail is fine */
  }
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
 * Persistence uses localStorage. The map is pruned of entries older
 * than 7 days on each load — long enough to debounce the "seen" rule
 * across sessions, short enough to keep the payload small.
 */
export function useSeenSponds() {
  const [seen, setSeen] = useState<SeenMap>({});

  useEffect(() => {
    setSeen(load());
  }, []);

  const markSeen = useCallback((spondId: string) => {
    setSeen((prev) => {
      if (prev[spondId]) return prev;
      const next = { ...prev, [spondId]: Date.now() };
      save(next);
      return next;
    });
  }, []);

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
