// @vitest-environment jsdom
/**
 * The header's account control was the site-wide hydration mismatch.
 *
 * JAVASCRIPT-NEXTJS-2 in Sentry: 240 events, first seen in April, filed
 * against `/en/PAM/fundamentals` only because that is the URL that got
 * sampled. Reproducing it against production showed React error #418 on
 * every page, in every timezone, which pointed at the shared layout
 * rather than at any one route. Running the app in dev mode named the
 * component outright:
 *
 *     <LinkComponent href="/en/login" className="account-bu...">
 *   +   <a className="account-button account-button--login" ...>
 *   -   <div className="account-button-placeholder" aria-hidden="true">
 *
 * The server has no session, so it always renders the placeholder. The
 * client knew the answer on its very first render (React Query resolves
 * `isLoading` to false straight away when its persisted cache already
 * holds `auth-user`) and rendered the sign-in link instead, so the two
 * trees disagreed before a single effect had run.
 *
 * The invariant these tests pin: the first client render must not depend
 * on auth state, because the server cannot know it. Auth-dependent markup
 * appears only after mount.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { renderToString } from "react-dom/server";

const mockAuthState = vi.hoisted(() => ({
  current: {
    user: null as unknown,
    isAuthenticated: false,
    isLoading: false,
    logout: () => {},
  },
}));

vi.mock("../hooks/useAuth", () => ({
  useAuth: () => mockAuthState.current,
}));

vi.mock("../i18n", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    locale: "en",
  }),
}));

vi.mock("next/link", () => ({
  default: ({ children, href, className }: {
    children: React.ReactNode;
    href: string;
    className?: string;
  }) => (
    <a href={href} className={className}>
      {children}
    </a>
  ),
}));

vi.mock("./social/UserAvatar", () => ({
  UserAvatar: () => <span data-testid="avatar" />,
}));

vi.mock("./social/ProfileEditModal", () => ({
  ProfileEditModal: () => <div data-testid="profile-edit-modal" />,
}));

import { AccountButton } from "./AccountButton";

const SIGNED_OUT = {
  user: null,
  isAuthenticated: false,
  isLoading: false,
  logout: () => {},
};

const SIGNED_IN = {
  user: { handle: "alice", display_name: "Alice", email: "alice@x.com" },
  isAuthenticated: true,
  isLoading: false,
  logout: () => {},
};

beforeEach(() => {
  mockAuthState.current = SIGNED_OUT;
});

afterEach(cleanup);

describe("AccountButton hydration safety", () => {
  it("renders the placeholder on the server even when auth has resolved", () => {
    mockAuthState.current = SIGNED_OUT;
    const html = renderToString(<AccountButton />);
    expect(html).toContain("account-button-placeholder");
    expect(html).not.toContain("account-button--login");
  });

  it("renders the placeholder on the server for a signed-in user too", () => {
    mockAuthState.current = SIGNED_IN;
    const html = renderToString(<AccountButton />);
    expect(html).toContain("account-button-placeholder");
    expect(html).not.toContain("account-button-handle");
  });

  it("shows the sign-in link once mounted", () => {
    mockAuthState.current = SIGNED_OUT;
    render(<AccountButton />);
    expect(document.querySelector(".account-button--login")).not.toBeNull();
    expect(document.querySelector(".account-button-placeholder")).toBeNull();
  });

  it("shows the handle once mounted for a signed-in user", () => {
    mockAuthState.current = SIGNED_IN;
    render(<AccountButton />);
    expect(screen.getByText("@alice")).toBeTruthy();
  });

  it("keeps showing the placeholder while auth is still loading", () => {
    mockAuthState.current = { ...SIGNED_OUT, isLoading: true };
    render(<AccountButton />);
    expect(document.querySelector(".account-button-placeholder")).not.toBeNull();
  });
});
