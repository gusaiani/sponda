// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { SpondCard } from "./SpondCard";
import type { SpondPayload } from "../../hooks/useProfile";

afterEach(cleanup);

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={typeof href === "string" ? href : "#"} {...rest}>{children}</a>
  ),
}));

vi.mock("../../hooks/useAuth", () => ({
  useAuth: () => ({
    user: { handle: "bob", display_name: "Bob", bio: "", is_private: false },
    isAuthenticated: true,
  }),
}));

vi.mock("../../hooks/useSocialFeed", () => ({
  useLikeSpond: () => ({ mutate: vi.fn(), isPending: false }),
  useDeleteSpond: () => ({ mutate: vi.fn(), isPending: false }),
}));

vi.mock("../../hooks/useSeenSponds", () => ({
  useSeenSponds: () => ({ markSeen: vi.fn() }),
}));

const spond: SpondPayload = {
  id: "spond-1",
  author: { handle: "alice", display_name: "Alice", bio: "", is_private: false },
  body: "hello world",
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
};

let client: QueryClient;
function wrap(ui: React.ReactNode) {
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

beforeEach(() => {
  client?.clear();
});

describe("SpondCard", () => {
  it("renders as a bordered card by default", () => {
    const { container } = wrap(<SpondCard spond={spond} />);
    const article = container.querySelector("article")!;
    expect(article.style.border).toMatch(/1px solid/);
  });

  it("drops the card chrome when embedded", () => {
    const { container } = wrap(<SpondCard spond={spond} embedded />);
    const article = container.querySelector("article")!;
    expect(article.style.border).toBe("");
    expect(article.style.marginBottom).toBe("");
  });

  it("renders Responder as a permalink by default", () => {
    wrap(<SpondCard spond={spond} />);
    const link = screen.getByRole("link", { name: /Reply/i });
    expect(link).toHaveAttribute("href", "/en/spond/spond-1");
  });

  it("renders Responder as a button calling onReplyClick when provided", () => {
    const onReplyClick = vi.fn();
    wrap(<SpondCard spond={spond} onReplyClick={onReplyClick} />);
    expect(screen.queryByRole("link", { name: /Reply/i })).toBeNull();
    const button = screen.getByRole("button", { name: /Reply/i });
    fireEvent.click(button);
    expect(onReplyClick).toHaveBeenCalledTimes(1);
  });

  it("marks the reply control active when replyActive is set", () => {
    const { container } = wrap(
      <SpondCard spond={spond} onReplyClick={vi.fn()} replyActive />,
    );
    const button = screen.getByRole("button", { name: /Reply/i });
    expect(button.style.fontWeight).toBe("600");
    expect(container).toBeTruthy();
  });
});
