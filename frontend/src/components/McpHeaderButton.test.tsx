// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { McpHeaderButton } from "./McpHeaderButton";

afterEach(cleanup);

describe("McpHeaderButton", () => {
  it('renders a pill labeled "MCP"', () => {
    render(<McpHeaderButton onClick={vi.fn()} />);

    const button = screen.getByRole("button", { name: /MCP/ });
    expect(button.textContent).toContain("MCP");
    expect(button.classList.contains("app-header-mcp-link")).toBe(true);
  });

  it('renders a "New" badge inside the pill', () => {
    render(<McpHeaderButton onClick={vi.fn()} />);

    const button = screen.getByRole("button", { name: /MCP/ });
    const badge = button.querySelector(".app-header-mcp-new-badge");
    expect(badge).not.toBeNull();
    expect(badge!.textContent).toBe("New");
  });

  it("calls onClick when clicked", () => {
    const onClick = vi.fn();
    render(<McpHeaderButton onClick={onClick} />);

    fireEvent.click(screen.getByRole("button", { name: /MCP/ }));

    expect(onClick).toHaveBeenCalledTimes(1);
  });
});
