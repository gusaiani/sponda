import { describe, it, expect, vi } from "vitest";
import {
  PERSISTED_QUERY_CACHE_KEY,
  clearPersistedAuthState,
} from "./clearPersistedAuthState";

interface MockArgs {
  queryClient: { clear: () => void };
  storage: { removeItem: (key: string) => void };
  navigator: { href: string };
}

function makeArgs(overrides: Partial<MockArgs> = {}): MockArgs {
  return {
    queryClient: overrides.queryClient ?? { clear: vi.fn() },
    storage: overrides.storage ?? { removeItem: vi.fn() },
    navigator: overrides.navigator ?? { href: "/somewhere" },
  };
}

describe("clearPersistedAuthState", () => {
  it("empties the in-memory React Query cache so any stale user-scoped data goes away", () => {
    const queryClient = { clear: vi.fn() };
    clearPersistedAuthState(makeArgs({ queryClient }));
    expect(queryClient.clear).toHaveBeenCalledOnce();
  });

  it("deletes the persisted React Query cache from storage so the next page load cannot rehydrate stale auth state", () => {
    const storage = { removeItem: vi.fn() };
    clearPersistedAuthState(makeArgs({ storage }));
    expect(storage.removeItem).toHaveBeenCalledWith(PERSISTED_QUERY_CACHE_KEY);
  });

  it("forces a hard navigation to the homepage so React Query starts fresh", () => {
    const navigator = { href: "/account" };
    clearPersistedAuthState(makeArgs({ navigator }));
    expect(navigator.href).toBe("/");
  });

  it("runs storage cleanup before the navigation assignment so the new page can't read the stale key", () => {
    const order: string[] = [];
    const storage = {
      removeItem: vi.fn(() => {
        order.push("removeItem");
      }),
    };
    const navigator = {
      get href() {
        return "/before";
      },
      set href(_value: string) {
        order.push("navigate");
      },
    };
    clearPersistedAuthState(
      makeArgs({ storage, navigator: navigator as unknown as { href: string } }),
    );
    expect(order).toEqual(["removeItem", "navigate"]);
  });
});
