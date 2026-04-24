// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render } from "@testing-library/react";

afterEach(cleanup);

const { mockPathname, mockPush, mockInvalidateQueries } = vi.hoisted(() => ({
  mockPathname: vi.fn(),
  mockPush: vi.fn(),
  mockInvalidateQueries: vi.fn(),
}));

vi.mock("next/image", () => ({
  default: ({ alt, ...props }: { alt: string }) => <img alt={alt} {...props} />,
}));

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => mockPathname(),
  useRouter: () => ({ push: mockPush }),
}));

vi.mock("@tanstack/react-query", () => ({
  useQueryClient: () => ({ invalidateQueries: mockInvalidateQueries }),
}));

vi.mock("../components/SearchBar", () => ({
  SearchBar: () => <div data-testid="search-bar" />,
}));

vi.mock("../components/AuthHeader", () => ({
  AuthHeader: () => <div className="auth-header" data-testid="auth-header" />,
}));

vi.mock("../components/FeedbackButton", () => ({
  FeedbackButton: () => <div data-testid="feedback-button" />,
}));

vi.mock("../i18n", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    locale: "en",
  }),
}));

vi.mock("../utils/branding", () => ({
  POEMA_RETURN: "10%",
  IBOVESPA_RETURN: "8%",
  POEMA_PERIOD: "2024",
}));

import { LayoutShell } from "./layout-shell";

describe("LayoutShell", () => {
  beforeEach(() => {
    mockPathname.mockReturnValue("/en/PETR4");
    mockPush.mockClear();
    mockInvalidateQueries.mockClear();
  });

  it("renders the SPONDA header brand on auth pages", () => {
    mockPathname.mockReturnValue("/en/login");

    render(<LayoutShell><div>Login content</div></LayoutShell>);

    const authHeader = document.querySelector(".app-header-auth");
    expect(authHeader).not.toBeNull();
    expect(authHeader!.querySelector(".app-header-logo")?.textContent).toBe("SPONDA");
    expect(authHeader!.querySelector('[data-testid="auth-header"]')).not.toBeNull();
    expect(document.querySelector('[data-testid="search-bar"]')).toBeNull();
    expect(authHeader!.textContent).not.toContain("screener.link_label");
  });

  it("keeps the full header on non-auth pages", () => {
    render(<LayoutShell><div>Company content</div></LayoutShell>);

    const header = document.querySelector(".app-header");
    expect(header).not.toBeNull();
    expect(header!.classList.contains("app-header-auth")).toBe(false);
    expect(header!.querySelector(".app-header-logo")?.textContent).toBe("SPONDA");
    expect(document.querySelector('[data-testid="search-bar"]')).not.toBeNull();
    expect(header!.textContent).toContain("screener.link_label");
  });
});
