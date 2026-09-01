// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { NotificationBell } from "./NotificationBell";
import type { SocialNotification } from "../hooks/useSocialNotifications";
import type { AlertNotificationEntry } from "../hooks/useAlertNotifications";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  mockAlertData.current = { count: 0, notifications: [] };
});

const mockSocialData = vi.hoisted(() => ({
  current: { unread_count: 0, notifications: [] as SocialNotification[] },
}));

const mockAlertData = vi.hoisted(() => ({
  current: { count: 0, notifications: [] as AlertNotificationEntry[] },
}));

vi.mock("next/link", () => ({
  default: ({ children, ...props }: { children: React.ReactNode }) => (
    <a {...props}>{children}</a>
  ),
}));

vi.mock("../hooks/useAuth", () => ({
  useAuth: () => ({ isAuthenticated: true }),
}));

vi.mock("../hooks/useAlertNotifications", () => ({
  useAlertNotifications: () => ({
    count: mockAlertData.current.count,
    notifications: mockAlertData.current.notifications,
    dismissNotification: { mutate: vi.fn(), isPending: false },
    dismissAllNotifications: { mutate: vi.fn(), isPending: false },
  }),
}));

vi.mock("../hooks/useVisits", () => ({
  usePendingReminders: () => ({
    count: 0,
    schedules: [],
    dismissReminder: { mutate: vi.fn(), isPending: false },
    dismissAllReminders: { mutate: vi.fn(), isPending: false },
  }),
}));

vi.mock("../hooks/useFollow", () => ({
  useFollowRequestAction: () => ({ mutate: vi.fn(), isPending: false }),
}));

vi.mock("../hooks/useSocialNotifications", () => ({
  useSocialNotifications: () => ({ data: mockSocialData.current }),
  useMarkNotificationsRead: () => ({ mutate: vi.fn(), isPending: false }),
}));

vi.mock("./social/UserAvatar", () => ({
  UserAvatar: () => <div data-testid="avatar" />,
}));

vi.mock("../i18n", () => ({
  useTranslation: () => ({
    t: (key: string, params?: Record<string, string | number>) =>
      params ? `${key}:${JSON.stringify(params)}` : key,
    locale: "pt",
  }),
}));

function makeFollowRequest(readAt: string | null): SocialNotification {
  return {
    id: 1,
    verb: "follow_requested",
    actor: { handle: "rodrigo", display_name: "Rodrigo", bio: "", is_private: false },
    target_type: "follow",
    target_id: "7",
    read_at: readAt,
    created_at: "2026-07-19T10:00:00Z",
  };
}

function makeAlertNotification(overrides: Partial<AlertNotificationEntry> = {}): AlertNotificationEntry {
  return {
    id: 1,
    ticker: "PETR4",
    indicator: "market_cap",
    comparison: "lte",
    threshold: "3000000000.000000",
    indicator_value: "2900000000.000000",
    dismissed_at: null,
    created_at: "2026-07-19T10:00:00Z",
    ...overrides,
  };
}

describe("NotificationBell triggered alert rows", () => {
  it("formats a market cap threshold in millions of the ticker's currency", () => {
    mockAlertData.current = { count: 1, notifications: [makeAlertNotification()] };
    render(<NotificationBell />);
    fireEvent.click(screen.getByRole("button", { name: "notifications.title" }));

    const row = document.querySelector(".notification-bell-status") as HTMLElement;
    expect(row.textContent).toContain("R$ 3.000M");
    expect(row.textContent).not.toContain("3000000000");
  });
});

describe("NotificationBell visibility", () => {
  it("renders nothing when there are no notifications at all", () => {
    mockSocialData.current = { unread_count: 0, notifications: [] };
    render(<NotificationBell />);
    expect(screen.queryByRole("button", { name: "notifications.title" })).toBeNull();
  });

  it("stays visible for a pending follow request even with zero unread", () => {
    // The bell is the only accept/reject UI. The backend keeps a pending
    // follow_requested visible after mark-all-read; the bell must not
    // vanish just because the unread badge count dropped to zero.
    mockSocialData.current = {
      unread_count: 0,
      notifications: [makeFollowRequest("2026-07-19T11:00:00Z")],
    };
    render(<NotificationBell />);
    expect(screen.getByRole("button", { name: "notifications.title" })).toBeTruthy();
  });

  it("hides the numeric badge when the unread count is zero", () => {
    mockSocialData.current = {
      unread_count: 0,
      notifications: [makeFollowRequest("2026-07-19T11:00:00Z")],
    };
    render(<NotificationBell />);
    expect(document.querySelector(".notification-bell-badge")).toBeNull();
  });

  it("shows the badge with the unread count when there are unread items", () => {
    mockSocialData.current = {
      unread_count: 2,
      notifications: [makeFollowRequest(null)],
    };
    render(<NotificationBell />);
    expect(document.querySelector(".notification-bell-badge")?.textContent).toBe("2");
  });
});
