// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render } from "@testing-library/react";
import { AuthHeader } from "./AuthHeader";

afterEach(cleanup);

vi.mock("./NotificationBell", () => ({
  NotificationBell: () => <div data-testid="notification-bell" />,
}));

vi.mock("./AccountButton", () => ({
  AccountButton: () => <div data-testid="account-button" />,
}));

describe("AuthHeader", () => {
  it("renders the notification bell and account button", () => {
    render(<AuthHeader />);
    expect(document.querySelector('[data-testid="notification-bell"]')).not.toBeNull();
    expect(document.querySelector('[data-testid="account-button"]')).not.toBeNull();
  });

  it("uses .auth-header class for layout integration", () => {
    render(<AuthHeader />);
    expect(document.querySelector(".auth-header")).not.toBeNull();
  });
});
