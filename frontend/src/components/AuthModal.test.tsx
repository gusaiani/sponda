// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { AuthModal } from "./AuthModal";

afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
  window.sessionStorage.clear();
});

const { setEmailVerificationPromptVisible } = vi.hoisted(() => ({
  setEmailVerificationPromptVisible: vi.fn(),
}));

vi.mock("../utils/emailVerificationPrompt", () => ({
  setEmailVerificationPromptVisible,
}));

describe("AuthModal", () => {
  const defaultProps = {
    onSuccess: vi.fn(),
    onClose: vi.fn(),
  };

  it("renders the mode toggle with login and signup buttons", () => {
    render(<AuthModal {...defaultProps} />);

    const toggle = document.querySelector(".auth-mode-toggle");
    expect(toggle).not.toBeNull();

    const buttons = toggle!.querySelectorAll("button");
    expect(buttons).toHaveLength(2);
    expect(buttons[0].textContent).toBe("Log in");
    expect(buttons[1].textContent).toBe("Sign up");
  });

  it("starts in login mode with login button active", () => {
    render(<AuthModal {...defaultProps} />);

    const toggle = document.querySelector(".auth-mode-toggle");
    const loginButton = toggle!.querySelector(".auth-mode-active");
    expect(loginButton).not.toBeNull();
    expect(loginButton!.textContent).toBe("Log in");
  });

  it("renders the contextual message when provided", () => {
    const message = "To save your card layout, log in or create a free account.";

    render(<AuthModal {...defaultProps} message={message} />);

    const messageElement = screen.getByText(message);
    expect(messageElement).toBeTruthy();
    expect(messageElement.classList.contains("auth-modal-message")).toBe(true);
  });

  it("does not render a message element when message is undefined", () => {
    render(<AuthModal {...defaultProps} />);

    const messageElements = document.querySelectorAll(".auth-modal-message");
    expect(messageElements).toHaveLength(0);
  });

  it("renders email and password inputs", () => {
    render(<AuthModal {...defaultProps} />);

    expect(screen.getByLabelText("Email")).toBeTruthy();
    expect(screen.getByLabelText("Password")).toBeTruthy();
  });

  it("renders Google sign-in button", () => {
    render(<AuthModal {...defaultProps} />);

    expect(screen.getByText("Continue with Google")).toBeTruthy();
  });

  it("renders the close button", () => {
    render(<AuthModal {...defaultProps} />);

    const closeButton = screen.getByLabelText("Close");
    expect(closeButton).toBeTruthy();
  });

  describe("Google sign-in", () => {
    function stubLocation(pathname: string, search = "") {
      Object.defineProperty(window, "location", {
        value: { ...window.location, href: "", origin: "http://localhost:3000", pathname, search },
        writable: true,
      });
    }

    it("remembers the current page so the callback can return to it", () => {
      vi.stubEnv("NEXT_PUBLIC_GOOGLE_CLIENT_ID", "client-id");
      stubLocation("/pt/VALE3", "?tab=charts");

      render(<AuthModal {...defaultProps} />);
      fireEvent.click(screen.getByText("Continue with Google"));

      const stored = JSON.parse(window.sessionStorage.getItem("sponda.postLoginReturn")!);
      expect(stored.path).toBe("/pt/VALE3?tab=charts");
      expect(window.location.href).toContain("accounts.google.com");
    });

    it("remembers the pending action so the page can resume it after login", () => {
      vi.stubEnv("NEXT_PUBLIC_GOOGLE_CLIENT_ID", "client-id");
      stubLocation("/pt/VALE3");

      render(
        <AuthModal {...defaultProps} pendingAction={{ kind: "mark-visited", ticker: "VALE3" }} />,
      );
      fireEvent.click(screen.getByText("Continue with Google"));

      const stored = JSON.parse(window.sessionStorage.getItem("sponda.pendingAuthAction")!);
      expect(stored.kind).toBe("mark-visited");
      expect(stored.ticker).toBe("VALE3");
    });
  });
});
