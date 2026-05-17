// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { SpondComposer } from "./SpondComposer";

afterEach(cleanup);

vi.mock("../../hooks/useAuth", () => ({
  useAuth: () => ({
    user: {
      handle: "alice",
      display_name: "Alice",
      email: "alice@x.com",
      email_verified: true,
      bio: "",
      is_private: false,
      is_superuser: false,
      date_joined: "2025-01-01",
      allow_contact: true,
    },
    isAuthenticated: true,
    isSuperuser: false,
    isLoading: false,
    showEmailVerificationPrompt: false,
    logout: vi.fn(),
    refreshUser: vi.fn(),
  }),
}));

const mutate = vi.fn();
vi.mock("../../hooks/useSocialFeed", () => ({
  useCreateSpond: () => ({
    mutateAsync: mutate,
    isPending: false,
  }),
}));

let client: QueryClient;
function wrap(ui: React.ReactNode) {
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

beforeEach(() => {
  mutate.mockReset();
  mutate.mockResolvedValue({});
});

// The composer is collapsed (single-line, no footer) until the textarea
// is focused or has content. Tests that need the footer present must
// focus the textarea first.
function focusTextarea(): HTMLTextAreaElement {
  const textarea = document.querySelector("textarea")! as HTMLTextAreaElement;
  fireEvent.focus(textarea);
  return textarea;
}

describe("SpondComposer", () => {
  it("renders char counter starting at 500 once focused", () => {
    wrap(<SpondComposer />);
    focusTextarea();
    expect(screen.getByText("500 characters left")).toBeInTheDocument();
  });

  it("decrements char counter as user types", () => {
    wrap(<SpondComposer />);
    const textarea = focusTextarea();
    fireEvent.change(textarea, { target: { value: "hello" } });
    expect(screen.getByText("495 characters left")).toBeInTheDocument();
  });

  it("disables submit when body is empty", () => {
    wrap(<SpondComposer />);
    focusTextarea();
    const button = screen.getByRole("button", { name: /Spond/i });
    expect(button).toBeDisabled();
  });

  it("disables submit when over 500 chars", () => {
    wrap(<SpondComposer />);
    const textarea = focusTextarea();
    fireEvent.change(textarea, { target: { value: "x".repeat(501) } });
    const button = screen.getByRole("button", { name: /Spond/i });
    expect(button).toBeDisabled();
  });

  it("shows the locked ticker chip when lockedTicker is provided", () => {
    wrap(<SpondComposer lockedTicker="PETR4" />);
    focusTextarea();
    expect(screen.getByText("$PETR4")).toBeInTheDocument();
  });

  it("starts collapsed when not focused and empty", () => {
    wrap(<SpondComposer />);
    expect(screen.queryByText("500 characters left")).toBeNull();
    expect(screen.queryByRole("button", { name: /Spond/i })).toBeNull();
  });

  it("calls mutateAsync when submitted with valid body", async () => {
    wrap(<SpondComposer />);
    fireEvent.change(document.querySelector("textarea")!, { target: { value: "hi there" } });
    fireEvent.submit(document.querySelector("textarea")!.closest("form")!);
    expect(mutate).toHaveBeenCalledWith({
      body: "hi there", ticker: undefined, parent: undefined,
    });
  });
});
