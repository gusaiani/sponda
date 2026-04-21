// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/react";

type TestAuthUser = {
  email: string;
  is_superuser: boolean;
  email_verified: boolean;
  date_joined: string;
  allow_contact: boolean;
};

const authState = {
  user: {
    email: "user@example.com",
    is_superuser: false,
    email_verified: true,
    date_joined: "2025-01-01T00:00:00Z",
    allow_contact: false,
  } as TestAuthUser | null,
  isAuthenticated: true,
  isLoading: false,
  logout: vi.fn(),
  refreshUser: vi.fn(),
};

vi.mock("../../../hooks/useAuth", () => ({
  useAuth: () => authState,
}));

vi.mock("../../../i18n", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    locale: "pt",
    pluralize: (_count: number, _singular: string, plural: string) => plural,
  }),
}));

vi.mock("../../../utils/csrf", () => ({
  csrfHeaders: () => ({ "Content-Type": "application/json", "X-CSRFToken": "test-csrf" }),
}));

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

import AccountPage from "./page";

beforeEach(() => {
  authState.user = {
    email: "user@example.com",
    is_superuser: false,
    email_verified: true,
    date_joined: "2025-01-01T00:00:00Z",
    allow_contact: false,
  };
  authState.isAuthenticated = true;
  authState.isLoading = false;
  authState.logout = vi.fn();
  authState.refreshUser = vi.fn();
  vi.stubGlobal("fetch", vi.fn());
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("AccountPage delete-account flow", () => {
  it("shows a delete-account entry on the main view", () => {
    render(<AccountPage />);
    expect(screen.getByRole("button", { name: "auth.delete_account" })).toBeTruthy();
  });

  it("navigates to the delete-account view and renders the warning and email prompt", () => {
    render(<AccountPage />);

    fireEvent.click(screen.getByRole("button", { name: "auth.delete_account" }));

    expect(screen.getByText("auth.delete_account_title")).toBeTruthy();
    expect(screen.getByText("auth.delete_account_warning")).toBeTruthy();
    expect(screen.getByLabelText("auth.delete_account_type_email")).toBeTruthy();
  });

  it("disables the confirm button until the typed email matches the account email", () => {
    render(<AccountPage />);
    fireEvent.click(screen.getByRole("button", { name: "auth.delete_account" }));

    const confirmButton = screen.getByRole("button", { name: "auth.delete_account_button" }) as HTMLButtonElement;
    const input = screen.getByLabelText("auth.delete_account_type_email") as HTMLInputElement;

    expect(confirmButton.disabled).toBe(true);

    fireEvent.change(input, { target: { value: "wrong@example.com" } });
    expect(confirmButton.disabled).toBe(true);

    fireEvent.change(input, { target: { value: "user@example.com" } });
    expect(confirmButton.disabled).toBe(false);
  });

  it("calls DELETE /api/auth/delete-account/ with the typed email when confirming", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 204, json: async () => ({}) });
    vi.stubGlobal("fetch", fetchMock);

    render(<AccountPage />);
    fireEvent.click(screen.getByRole("button", { name: "auth.delete_account" }));
    fireEvent.change(screen.getByLabelText("auth.delete_account_type_email"), {
      target: { value: "user@example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: "auth.delete_account_button" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());

    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/auth/delete-account/");
    expect(options.method).toBe("DELETE");
    expect(options.credentials).toBe("include");
    expect(JSON.parse(options.body)).toEqual({ email_confirmation: "user@example.com" });
  });

  it("shows an error message when the server rejects the deletion", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      json: async () => ({ error: "server-error" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<AccountPage />);
    fireEvent.click(screen.getByRole("button", { name: "auth.delete_account" }));
    fireEvent.change(screen.getByLabelText("auth.delete_account_type_email"), {
      target: { value: "user@example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: "auth.delete_account_button" }));

    await waitFor(() => expect(screen.getByText("server-error")).toBeTruthy());
  });
});

describe("AccountPage change-email flow", () => {
  it("shows a change-email entry on the main view", () => {
    render(<AccountPage />);
    expect(screen.getByRole("button", { name: "auth.change_email" })).toBeTruthy();
  });

  it("navigates to the change-email view and shows the form", () => {
    render(<AccountPage />);

    fireEvent.click(screen.getByRole("button", { name: "auth.change_email" }));

    expect(screen.getByText("auth.change_email_title")).toBeTruthy();
    expect(screen.getByLabelText("auth.new_email")).toBeTruthy();
    expect(screen.getByLabelText("auth.current_password")).toBeTruthy();
  });

  it("submits POST to /api/auth/change-email/ with new_email and password", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ email: "new@example.com", email_verified: false }),
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<AccountPage />);
    fireEvent.click(screen.getByRole("button", { name: "auth.change_email" }));
    fireEvent.change(screen.getByLabelText("auth.new_email"), {
      target: { value: "new@example.com" },
    });
    fireEvent.change(screen.getByLabelText("auth.current_password"), {
      target: { value: "mypassword" },
    });
    fireEvent.click(screen.getByRole("button", { name: "auth.change_email_button" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());

    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/auth/change-email/");
    expect(options.method).toBe("POST");
    expect(JSON.parse(options.body)).toEqual({
      new_email: "new@example.com",
      password: "mypassword",
    });
  });

  it("shows a verification-sent message after a successful change-email", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ email: "new@example.com", email_verified: false }),
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<AccountPage />);
    fireEvent.click(screen.getByRole("button", { name: "auth.change_email" }));
    fireEvent.change(screen.getByLabelText("auth.new_email"), {
      target: { value: "new@example.com" },
    });
    fireEvent.change(screen.getByLabelText("auth.current_password"), {
      target: { value: "mypassword" },
    });
    fireEvent.click(screen.getByRole("button", { name: "auth.change_email_button" }));

    await waitFor(() =>
      expect(screen.getByText("auth.change_email_verification_sent")).toBeTruthy()
    );
    expect(authState.refreshUser).toHaveBeenCalled();
  });

  it("shows the server error when change-email fails", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      json: async () => ({ error: "email-already-taken" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<AccountPage />);
    fireEvent.click(screen.getByRole("button", { name: "auth.change_email" }));
    fireEvent.change(screen.getByLabelText("auth.new_email"), {
      target: { value: "new@example.com" },
    });
    fireEvent.change(screen.getByLabelText("auth.current_password"), {
      target: { value: "mypassword" },
    });
    fireEvent.click(screen.getByRole("button", { name: "auth.change_email_button" }));

    await waitFor(() => expect(screen.getByText("email-already-taken")).toBeTruthy());
  });
});

describe("AccountPage resend verification", () => {
  it("hides the resend verification button when email is already verified", () => {
    render(<AccountPage />);
    expect(
      screen.queryByRole("button", { name: "auth.resend_verification" })
    ).toBeNull();
  });

  it("shows a resend verification button when email is not verified", () => {
    authState.user = {
      email: "user@example.com",
      is_superuser: false,
      email_verified: false,
      date_joined: "2025-01-01T00:00:00Z",
      allow_contact: false,
    };

    render(<AccountPage />);
    expect(
      screen.getByRole("button", { name: "auth.resend_verification" })
    ).toBeTruthy();
    expect(screen.getByText("auth.email_not_verified_note")).toBeTruthy();
  });

  it("POSTs to /api/auth/resend-verification/ and shows a success message", async () => {
    authState.user = {
      email: "user@example.com",
      is_superuser: false,
      email_verified: false,
      date_joined: "2025-01-01T00:00:00Z",
      allow_contact: false,
    };
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ ok: true }),
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<AccountPage />);
    fireEvent.click(screen.getByRole("button", { name: "auth.resend_verification" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());

    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/auth/resend-verification/");
    expect(options.method).toBe("POST");
    expect(options.credentials).toBe("include");

    await waitFor(() =>
      expect(screen.getByText("auth.resend_verification_sent")).toBeTruthy()
    );
  });

  it("shows an error message when the resend request fails", async () => {
    authState.user = {
      email: "user@example.com",
      is_superuser: false,
      email_verified: false,
      date_joined: "2025-01-01T00:00:00Z",
      allow_contact: false,
    };
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({}),
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<AccountPage />);
    fireEvent.click(screen.getByRole("button", { name: "auth.resend_verification" }));

    await waitFor(() =>
      expect(screen.getByText("auth.resend_verification_error")).toBeTruthy()
    );
  });
});

describe("AccountPage preferences toggle", () => {
  it("renders the allow_contact checkbox reflecting the current user preference", () => {
    authState.user = {
      email: "user@example.com",
      is_superuser: false,
      email_verified: true,
      date_joined: "2025-01-01T00:00:00Z",
      allow_contact: true,
    };

    render(<AccountPage />);
    const checkbox = screen.getByLabelText("auth.allow_contact") as HTMLInputElement;
    expect(checkbox.checked).toBe(true);
  });

  it("PATCHes /api/auth/preferences/ when the allow_contact checkbox is toggled", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ allow_contact: true }),
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<AccountPage />);
    const checkbox = screen.getByLabelText("auth.allow_contact") as HTMLInputElement;
    fireEvent.click(checkbox);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());

    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/auth/preferences/");
    expect(options.method).toBe("PATCH");
    expect(JSON.parse(options.body)).toEqual({ allow_contact: true });
  });

  it("shows a 'saving' state while the PATCH is in flight and 'saved' on success", async () => {
    let resolveFetch: ((value: unknown) => void) | null = null;
    const fetchMock = vi.fn().mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveFetch = resolve;
        })
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<AccountPage />);
    const checkbox = screen.getByLabelText("auth.allow_contact") as HTMLInputElement;
    fireEvent.click(checkbox);

    expect(screen.getByText("auth.preferences_saving")).toBeTruthy();

    resolveFetch!({
      ok: true,
      status: 200,
      json: async () => ({ allow_contact: true }),
    });

    await waitFor(() => expect(screen.getByText("auth.preferences_saved")).toBeTruthy());
  });

  it("reverts the checkbox and shows an error if the PATCH fails", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({}),
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<AccountPage />);
    const checkbox = screen.getByLabelText("auth.allow_contact") as HTMLInputElement;
    expect(checkbox.checked).toBe(false);
    fireEvent.click(checkbox);

    await waitFor(() =>
      expect(screen.getByText("auth.preferences_update_error")).toBeTruthy()
    );
    expect(checkbox.checked).toBe(false);
  });
});
