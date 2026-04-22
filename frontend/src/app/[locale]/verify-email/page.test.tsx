// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import VerifyEmailPage from "./page";

const mockUseAuth = vi.fn();
const mockUseSearchParams = vi.fn();

vi.mock("next/navigation", () => ({
  useSearchParams: () => mockUseSearchParams(),
}));

vi.mock("../../../hooks/useAuth", () => ({
  useAuth: () => mockUseAuth(),
}));

vi.mock("../../../utils/csrf", () => ({
  csrfHeaders: () => ({ "X-CSRFToken": "token" }),
}));

vi.mock("../../../i18n", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    locale: "en",
  }),
}));

describe("VerifyEmailPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    mockUseSearchParams.mockReturnValue(new URLSearchParams());
    mockUseAuth.mockReturnValue({
      user: { email_verified: false },
      isLoading: false,
      isAuthenticated: true,
      refreshUser: vi.fn(),
    });
  });

  it("shows resend verification actions when an unverified user visits without a token", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchMock);
    const queryClient = new QueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <VerifyEmailPage />
      </QueryClientProvider>,
    );

    expect(await screen.findByText("verify.pending_title")).toBeTruthy();
    expect(screen.getByText("verify.pending_text")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "auth.resend_verification" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith("/api/auth/resend-verification/", expect.objectContaining({
        method: "POST",
        credentials: "include",
      }));
    });

    expect(await screen.findByText("auth.resend_verification_sent")).toBeTruthy();
  });
});
