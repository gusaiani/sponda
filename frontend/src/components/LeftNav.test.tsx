// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { LeftNav } from "./LeftNav";

afterEach(cleanup);

const mockIsAuthenticated = vi.fn(() => false);
const mockIsSuperuser = vi.fn(() => false);

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: React.ComponentProps<"a">) => (
    <a href={typeof href === "string" ? href : String(href)} {...props}>
      {children}
    </a>
  ),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/en",
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("../i18n", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    locale: "en",
    setLocale: vi.fn(),
  }),
}));

vi.mock("../hooks/useAuth", () => ({
  useAuth: () => ({
    isAuthenticated: mockIsAuthenticated(),
    isSuperuser: mockIsSuperuser(),
  }),
}));

vi.mock("../learning", () => ({
  useLearningMode: () => ({
    available: false,
    enabled: false,
    setEnabled: vi.fn(),
  }),
}));

vi.mock("./FeedbackButton", () => ({
  useFeedback: () => ({ open: vi.fn() }),
}));

vi.mock("./LeftNavContext", () => ({
  useLeftNav: () => ({ open: true, setOpen: vi.fn() }),
}));

vi.mock("../styles/left-nav.css", () => ({}));

describe("LeftNav superuser links", () => {
  it("shows the MCP calls audit-log link to superusers", () => {
    mockIsAuthenticated.mockReturnValue(true);
    mockIsSuperuser.mockReturnValue(true);

    render(<LeftNav />);

    const link = screen.getByRole("link", { name: /MCP calls/ });
    expect(link.getAttribute("href")).toBe("/admin/assistant/mcpcall/");
  });

  it("shows the admin dashboard link to superusers", () => {
    mockIsAuthenticated.mockReturnValue(true);
    mockIsSuperuser.mockReturnValue(true);

    render(<LeftNav />);

    expect(screen.getByRole("link", { name: "Admin" })).toBeTruthy();
  });

  it("hides both admin links from signed-in non-superusers", () => {
    mockIsAuthenticated.mockReturnValue(true);
    mockIsSuperuser.mockReturnValue(false);

    render(<LeftNav />);

    expect(screen.queryByRole("link", { name: /MCP calls/ })).toBeNull();
    expect(screen.queryByRole("link", { name: "Admin" })).toBeNull();
  });

  it("hides both admin links from anonymous visitors", () => {
    mockIsAuthenticated.mockReturnValue(false);
    mockIsSuperuser.mockReturnValue(false);

    render(<LeftNav />);

    expect(screen.queryByRole("link", { name: /MCP calls/ })).toBeNull();
    expect(screen.queryByRole("link", { name: "Admin" })).toBeNull();
  });
});
