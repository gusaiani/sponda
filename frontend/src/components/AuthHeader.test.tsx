// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, cleanup, fireEvent } from "@testing-library/react";
import { AuthHeader } from "./AuthHeader";

afterEach(cleanup);

const mockUseAuth = vi.fn();
const mockPathname = vi.fn();

vi.mock("../hooks/useAuth", () => ({
  useAuth: () => mockUseAuth(),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => mockPathname(),
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("../i18n", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    locale: "en",
  }),
  LanguageToggle: () => <div data-testid="language-toggle" />,
}));

vi.mock("./ShareDropdown", () => ({
  ShareDropdown: () => <div data-testid="share-dropdown" />,
}));

vi.mock("./NotificationBell", () => ({
  NotificationBell: () => <div data-testid="notification-bell" />,
}));

describe("AuthHeader mobile hamburger menu", () => {
  beforeEach(() => {
    mockPathname.mockReturnValue("/en/PETR4");
  });

  it("renders a hamburger button when authenticated", () => {
    mockUseAuth.mockReturnValue({ isAuthenticated: true, isSuperuser: false, isLoading: false });

    render(<AuthHeader />);
    const button = document.querySelector(".auth-header-hamburger");
    expect(button).not.toBeNull();
  });

  it("hides the hamburger menu by default", () => {
    mockUseAuth.mockReturnValue({ isAuthenticated: true, isSuperuser: false, isLoading: false });

    render(<AuthHeader />);
    expect(document.querySelector(".auth-header-menu")).toBeNull();
  });

  it("opens the menu on hamburger click and shows Share, Visitas, Account and language toggle", () => {
    mockUseAuth.mockReturnValue({ isAuthenticated: true, isSuperuser: false, isLoading: false });

    render(<AuthHeader />);
    fireEvent.click(document.querySelector(".auth-header-hamburger")!);

    const menu = document.querySelector(".auth-header-menu");
    expect(menu).not.toBeNull();
    expect(menu!.textContent).toContain("visits.page_title");
    expect(menu!.textContent).toContain("auth.my_account");
    expect(menu!.querySelector('[data-testid="language-toggle"]')).not.toBeNull();
    expect(menu!.querySelector('[data-testid="share-dropdown"]')).not.toBeNull();
  });

  it("shows the Login link in the menu for unauthenticated users", () => {
    mockUseAuth.mockReturnValue({ isAuthenticated: false, isSuperuser: false, isLoading: false });

    render(<AuthHeader />);
    fireEvent.click(document.querySelector(".auth-header-hamburger")!);

    const menu = document.querySelector(".auth-header-menu");
    expect(menu).not.toBeNull();
    const loginLink = menu!.querySelector(".auth-header-signup");
    expect(loginLink).not.toBeNull();
    expect(loginLink!.textContent).toBe("auth.login");
  });

  it("shows the Admin link in the menu only for superusers", () => {
    mockUseAuth.mockReturnValue({ isAuthenticated: true, isSuperuser: true, isLoading: false });

    render(<AuthHeader />);
    fireEvent.click(document.querySelector(".auth-header-hamburger")!);

    const menu = document.querySelector(".auth-header-menu");
    expect(menu!.textContent).toContain("Admin");
  });

  it("does not show the Admin link when the user is not a superuser", () => {
    mockUseAuth.mockReturnValue({ isAuthenticated: true, isSuperuser: false, isLoading: false });

    render(<AuthHeader />);
    fireEvent.click(document.querySelector(".auth-header-hamburger")!);

    const menu = document.querySelector(".auth-header-menu");
    expect(menu!.textContent).not.toContain("Admin");
  });

  it("renders the hamburger even when unauthenticated so language is reachable on mobile", () => {
    mockUseAuth.mockReturnValue({ isAuthenticated: false, isSuperuser: false, isLoading: false });

    render(<AuthHeader />);
    const button = document.querySelector(".auth-header-hamburger");
    expect(button).not.toBeNull();
  });

  it("renders the login link for unauthenticated users", () => {
    mockUseAuth.mockReturnValue({ isAuthenticated: false, isSuperuser: false, isLoading: false });

    render(<AuthHeader />);
    const loginLink = document.querySelector(".auth-header-signup");
    expect(loginLink).not.toBeNull();
    expect(loginLink!.textContent).toBe("auth.login");
  });
});
