// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";

import { SpondFeed } from "./SpondFeed";
import type { SpondPayload } from "../../hooks/useProfile";

afterEach(() => {
  cleanup();
  threadProps.length = 0;
});

// Capture the props each SpondThread receives so we can assert the feed
// opts every thread into inline replies — clicking "Responder" must open
// the composer underneath the Spond rather than navigate to the permalink.
const threadProps: { spond: SpondPayload; inlineReply?: boolean }[] = [];
vi.mock("./SpondThread", () => ({
  SpondThread: (props: { spond: SpondPayload; inlineReply?: boolean }) => {
    threadProps.push(props);
    return (
      <div
        data-testid={`thread-${props.spond.id}`}
        data-inline-reply={String(Boolean(props.inlineReply))}
      />
    );
  },
}));

const feedReturn: {
  isLoading: boolean;
  data: { pages: { results: SpondPayload[] }[] };
  hasNextPage: boolean;
  isFetchingNextPage: boolean;
  fetchNextPage: () => void;
} = {
  isLoading: false,
  data: { pages: [{ results: [] }] },
  hasNextPage: false,
  isFetchingNextPage: false,
  fetchNextPage: vi.fn(),
};

vi.mock("../../hooks/useSocialFeed", () => ({
  useSocialFeed: () => feedReturn,
}));

function makeSpond(overrides: Partial<SpondPayload> = {}): SpondPayload {
  return {
    id: "root",
    author: { handle: "gu", display_name: "Gu", bio: "", is_private: false },
    body: "WEGE3 caro",
    ticker: "",
    parent: null,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    is_within_edit_window: false,
    like_count: 0,
    reply_count: 0,
    viewer_has_liked: false,
    ticker_mentions: [],
    handle_mentions: [],
    ...overrides,
  };
}

describe("SpondFeed", () => {
  it("renders each thread with inline replies enabled", () => {
    feedReturn.data = {
      pages: [{ results: [makeSpond({ id: "a" }), makeSpond({ id: "b" })] }],
    };

    render(<SpondFeed kind="global" />);

    expect(screen.getByTestId("thread-a")).toHaveAttribute("data-inline-reply", "true");
    expect(screen.getByTestId("thread-b")).toHaveAttribute("data-inline-reply", "true");
    expect(threadProps.every((p) => p.inlineReply === true)).toBe(true);
  });
});
