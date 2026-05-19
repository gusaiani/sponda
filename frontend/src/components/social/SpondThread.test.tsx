// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { SpondThread } from "./SpondThread";
import type { SpondPayload } from "../../hooks/useProfile";

afterEach(cleanup);

// Stub the leaf components so these tests cover only SpondThread's
// orchestration: box grouping, composer toggle, lazy reply expansion.
vi.mock("./SpondCard", () => ({
  SpondCard: ({
    spond, onReplyClick, replyActive, embedded,
  }: {
    spond: SpondPayload;
    onReplyClick?: () => void;
    replyActive?: boolean;
    embedded?: boolean;
  }) => (
    <div data-testid={`card-${spond.id}`} data-embedded={String(Boolean(embedded))}>
      <span>{spond.body}</span>
      {onReplyClick && (
        <button type="button" onClick={onReplyClick}>
          {`card-reply${replyActive ? "-active" : ""}`}
        </button>
      )}
    </div>
  ),
}));

vi.mock("./SpondComposer", () => ({
  SpondComposer: ({
    parentId, parentHandle, inline, onSubmitted,
  }: {
    parentId?: string;
    parentHandle?: string;
    inline?: boolean;
    onSubmitted?: () => void;
  }) => (
    <div data-testid="composer" data-parent={parentId} data-inline={String(Boolean(inline))}>
      {`composer for @${parentHandle}`}
      <button type="button" onClick={() => onSubmitted?.()}>fake-submit</button>
    </div>
  ),
}));

function makeSpond(overrides: Partial<SpondPayload> = {}): SpondPayload {
  return {
    id: "root",
    author: { handle: "rodrigo", display_name: "rodrigo", bio: "", is_private: false },
    body: "AZZA3 ta uo",
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

let client: QueryClient;
function wrap(ui: React.ReactNode) {
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("SpondThread", () => {
  it("renders the root and provided replies inside one box, composer hidden", () => {
    const root = makeSpond({ id: "root", reply_count: 1 });
    const reply = makeSpond({ id: "r1", body: "eyes", parent: "root" });
    wrap(<SpondThread spond={root} replies={[reply]} inlineReply />);

    expect(screen.getByTestId("card-root")).toBeInTheDocument();
    expect(screen.getByTestId("card-r1")).toBeInTheDocument();
    expect(screen.queryByTestId("composer")).toBeNull();
  });

  it("toggles the inline composer when the root reply control is clicked", () => {
    const root = makeSpond({ id: "root" });
    wrap(<SpondThread spond={root} replies={[]} inlineReply />);

    fireEvent.click(screen.getByRole("button", { name: "card-reply" }));
    const composer = screen.getByTestId("composer");
    expect(composer).toHaveAttribute("data-parent", "root");
    expect(composer).toHaveAttribute("data-inline", "true");

    fireEvent.click(screen.getByRole("button", { name: "card-reply-active" }));
    expect(screen.queryByTestId("composer")).toBeNull();
  });

  it("closes the composer and calls onChanged after a reply is submitted", () => {
    const onChanged = vi.fn();
    wrap(
      <SpondThread spond={makeSpond()} replies={[]} inlineReply onChanged={onChanged} />,
    );
    fireEvent.click(screen.getByRole("button", { name: "card-reply" }));
    fireEvent.click(screen.getByRole("button", { name: "fake-submit" }));
    expect(onChanged).toHaveBeenCalledTimes(1);
    expect(screen.queryByTestId("composer")).toBeNull();
  });

  it("lazily fetches and nests replies when the toggle is clicked", async () => {
    const root = makeSpond({ id: "root", reply_count: 2 });
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        spond: root,
        replies: [
          makeSpond({ id: "r1", body: "first", parent: "root" }),
          makeSpond({ id: "r2", body: "second", parent: "root" }),
        ],
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    wrap(<SpondThread spond={root} />);

    expect(screen.queryByTestId("card-r1")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /Show 2 replies/i }));

    await waitFor(() => expect(screen.getByTestId("card-r1")).toBeInTheDocument());
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/social/sponds/root/",
      expect.objectContaining({ credentials: "include" }),
    );
    expect(screen.getByTestId("card-r2")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Hide replies/i }));
    expect(screen.queryByTestId("card-r1")).toBeNull();
  });

  it("shows no reply toggle when there are no replies", () => {
    wrap(<SpondThread spond={makeSpond({ reply_count: 0 })} />);
    expect(screen.queryByRole("button", { name: /replies/i })).toBeNull();
    expect(screen.queryByTestId("composer")).toBeNull();
    expect(screen.getByTestId("card-root")).toBeInTheDocument();
  });
});
