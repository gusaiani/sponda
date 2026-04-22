// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { AuthModal } from "./AuthModal";

afterEach(cleanup);

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

  it("shows a verification modal after successful signup", async () => {
    const onSuccess = vi.fn();
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ email: "new@example.com" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<AuthModal {...defaultProps} onSuccess={onSuccess} />);

    fireEvent.click(screen.getByRole("button", { name: "Sign up" }));
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "new@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "password123" } });
    fireEvent.change(screen.getByLabelText("Confirm Password"), { target: { value: "password123" } });
    fireEvent.click(screen.getByRole("button", { name: "Create Account" }));

    expect(await screen.findByText("Confirm your email")).toBeTruthy();
    expect(screen.getByText("Verification email sent. Check your inbox.")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(onSuccess).toHaveBeenCalled();
  });
});
