// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { SpondCard } from "./SpondCard";
import type { SpondPayload } from "../../hooks/useProfile";

afterEach(cleanup);

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={typeof href === "string" ? href : "#"} {...rest}>{children}</a>
  ),
}));

const { mockUser, mockRefreshUser, mockLikeMutate, mockPush } = vi.hoisted(() => ({
  mockUser: vi.fn(),
  mockRefreshUser: vi.fn(),
  mockLikeMutate: vi.fn(),
  mockPush: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

vi.mock("../../hooks/useAuth", () => ({
  useAuth: () => ({
    user: mockUser(),
    isAuthenticated: Boolean(mockUser()),
    refreshUser: mockRefreshUser,
  }),
}));

// Stubbed so these tests exercise SpondCard's orchestration, not the
// modal's own form (AuthModal has its own test file).
vi.mock("../AuthModal", () => ({
  AuthModal: ({ onSuccess, onClose }: { onSuccess: () => void; onClose: () => void }) => (
    <div data-testid="auth-modal">
      <button type="button" onClick={onSuccess}>stub-authenticate</button>
      <button type="button" onClick={onClose}>stub-close</button>
    </div>
  ),
}));

vi.mock("../../hooks/useSocialFeed", () => ({
  useLikeSpond: () => ({ mutate: mockLikeMutate, isPending: false }),
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

const signedInUser = { handle: "bob", display_name: "Bob", bio: "", is_private: false };

beforeEach(() => {
  client?.clear();
  mockUser.mockReturnValue(signedInUser);
  mockRefreshUser.mockClear();
  mockLikeMutate.mockClear();
  mockPush.mockClear();
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

  it("likes straight away for a signed-in user, with no auth modal", () => {
    wrap(<SpondCard spond={spond} />);
    fireEvent.click(screen.getByRole("button", { name: /Like/i }));
    expect(screen.queryByTestId("auth-modal")).toBeNull();
    expect(mockLikeMutate).toHaveBeenCalledWith(
      { id: "spond-1", like: true },
      expect.anything(),
    );
  });

  describe("signed out", () => {
    beforeEach(() => {
      mockUser.mockReturnValue(null);
    });

    it("offers Like as a live control rather than a disabled one", () => {
      wrap(<SpondCard spond={spond} />);
      expect(screen.getByRole("button", { name: /Like/i })).not.toBeDisabled();
    });

    it("opens the auth modal on Like instead of liking", () => {
      wrap(<SpondCard spond={spond} />);
      fireEvent.click(screen.getByRole("button", { name: /Like/i }));
      expect(screen.getByTestId("auth-modal")).toBeInTheDocument();
      expect(mockLikeMutate).not.toHaveBeenCalled();
    });

    it("completes the like once authentication succeeds", async () => {
      wrap(<SpondCard spond={spond} />);
      fireEvent.click(screen.getByRole("button", { name: /Like/i }));
      fireEvent.click(screen.getByText("stub-authenticate"));

      expect(mockRefreshUser).toHaveBeenCalled();
      await waitFor(() =>
        expect(mockLikeMutate).toHaveBeenCalledWith(
          { id: "spond-1", like: true },
          expect.anything(),
        ),
      );
      expect(screen.queryByTestId("auth-modal")).toBeNull();
    });

    it("abandons the pending like when the modal is dismissed", () => {
      wrap(<SpondCard spond={spond} />);
      fireEvent.click(screen.getByRole("button", { name: /Like/i }));
      fireEvent.click(screen.getByText("stub-close"));

      expect(screen.queryByTestId("auth-modal")).toBeNull();
      expect(mockLikeMutate).not.toHaveBeenCalled();
    });

    it("opens the auth modal on Reply, then opens the composer on success", async () => {
      const onReplyClick = vi.fn();
      wrap(<SpondCard spond={spond} onReplyClick={onReplyClick} />);

      fireEvent.click(screen.getByRole("button", { name: /Reply/i }));
      expect(screen.getByTestId("auth-modal")).toBeInTheDocument();
      expect(onReplyClick).not.toHaveBeenCalled();

      fireEvent.click(screen.getByText("stub-authenticate"));
      await waitFor(() => expect(onReplyClick).toHaveBeenCalledTimes(1));
    });

    it("sends Reply without an inline composer to the permalink ready to reply", async () => {
      wrap(<SpondCard spond={spond} />);

      fireEvent.click(screen.getByRole("button", { name: /Reply/i }));
      fireEvent.click(screen.getByText("stub-authenticate"));

      await waitFor(() =>
        expect(mockPush).toHaveBeenCalledWith("/en/spond/spond-1?reply=1"),
      );
    });
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
