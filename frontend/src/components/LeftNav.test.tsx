// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { LeftNav } from "./LeftNav";

afterEach(cleanup);

const mockIsAuthenticated = vi.fn(() => false);
const mockIsSuperuser = vi.fn(() => false);
const mockSetOpen = vi.fn();

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
  useLeftNav: () => ({ open: true, setOpen: mockSetOpen }),
}));

vi.mock("../styles/left-nav.css", () => ({}));

function renderLeftNav(onOpenMcpAnnouncement = vi.fn()) {
  return render(<LeftNav onOpenMcpAnnouncement={onOpenMcpAnnouncement} />);
}

describe("LeftNav MCP entry", () => {
  // The header MCP pill is hidden below 640px so the header fits one row;
  // the rail carries the entry point on those viewports instead.
  it("renders an MCP item flagged as mobile-only", () => {
    renderLeftNav();

    const item = screen.getByRole("button", { name: /MCP/ });
    expect(item.classList.contains("left-nav-item--mobile-only")).toBe(true);
    expect(item.querySelector(".left-nav-badge-new")!.textContent).toBe("mcp.eyebrow");
  });

  it("opens the announcement and closes the overlay rail when tapped on a phone", () => {
    const onOpenMcpAnnouncement = vi.fn();
    mockSetOpen.mockClear();
    window.innerWidth = 390;
    renderLeftNav(onOpenMcpAnnouncement);

    fireEvent.click(screen.getByRole("button", { name: /MCP/ }));

    expect(onOpenMcpAnnouncement).toHaveBeenCalledTimes(1);
    expect(mockSetOpen).toHaveBeenCalledWith(false);
  });
});

describe("LeftNav superuser links", () => {
  it("shows the MCP calls audit-log link to superusers", () => {
    mockIsAuthenticated.mockReturnValue(true);
    mockIsSuperuser.mockReturnValue(true);

    renderLeftNav();

    const link = screen.getByRole("link", { name: /MCP calls/ });
    expect(link.getAttribute("href")).toBe("/admin/assistant/mcpcall/");
  });

  it("shows the admin dashboard link to superusers", () => {
    mockIsAuthenticated.mockReturnValue(true);
    mockIsSuperuser.mockReturnValue(true);

    renderLeftNav();

    expect(screen.getByRole("link", { name: "Admin" })).toBeTruthy();
  });

  it("hides both admin links from signed-in non-superusers", () => {
    mockIsAuthenticated.mockReturnValue(true);
    mockIsSuperuser.mockReturnValue(false);

    renderLeftNav();

    expect(screen.queryByRole("link", { name: /MCP calls/ })).toBeNull();
    expect(screen.queryByRole("link", { name: "Admin" })).toBeNull();
  });

  it("hides both admin links from anonymous visitors", () => {
    mockIsAuthenticated.mockReturnValue(false);
    mockIsSuperuser.mockReturnValue(false);

    renderLeftNav();

    expect(screen.queryByRole("link", { name: /MCP calls/ })).toBeNull();
    expect(screen.queryByRole("link", { name: "Admin" })).toBeNull();
  });
});
