// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { AuthModal } from "./AuthModal";

afterEach(cleanup);

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
    expect(buttons[0].textContent).toBe("Entrar");
    expect(buttons[1].textContent).toBe("Criar conta");
  });

  it("starts in login mode with Entrar button active", () => {
    render(<AuthModal {...defaultProps} />);

    const toggle = document.querySelector(".auth-mode-toggle");
    const loginButton = toggle!.querySelector(".auth-mode-active");
    expect(loginButton).not.toBeNull();
    expect(loginButton!.textContent).toBe("Entrar");
  });

  it("renders the contextual message when provided", () => {
    const message = "Para salvar a organização dos seus cards, entre ou crie uma conta gratuita.";

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
    expect(screen.getByLabelText("Senha")).toBeTruthy();
  });

  it("renders Google sign-in button", () => {
    render(<AuthModal {...defaultProps} />);

    expect(screen.getByText("Continuar com Google")).toBeTruthy();
  });

  it("renders the close button", () => {
    render(<AuthModal {...defaultProps} />);

    const closeButton = screen.getByLabelText("Fechar");
    expect(closeButton).toBeTruthy();
  });
});
