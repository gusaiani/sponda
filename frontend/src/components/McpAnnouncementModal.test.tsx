// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { McpAnnouncementModal } from "./McpAnnouncementModal";

afterEach(cleanup);

const clipboardWriteText = vi.fn().mockResolvedValue(undefined);

beforeEach(() => {
  clipboardWriteText.mockClear();
  Object.defineProperty(navigator, "clipboard", {
    value: { writeText: clipboardWriteText },
    configurable: true,
  });
});

const CLAUDE_CODE_INSTALL_COMMAND =
  "claude mcp add --transport http sponda https://sponda.capital/api/mcp/";

describe("McpAnnouncementModal", () => {
  const defaultProps = { onClose: vi.fn() };

  it("renders the announcement title", () => {
    render(<McpAnnouncementModal {...defaultProps} />);

    expect(screen.getByText("Sponda is now an MCP server")).toBeTruthy();
  });

  it("shows the Claude Code install command by default", () => {
    render(<McpAnnouncementModal {...defaultProps} />);

    expect(screen.getByText(CLAUDE_CODE_INSTALL_COMMAND)).toBeTruthy();
  });

  it("switches to the Cursor tab and shows the JSON config", () => {
    render(<McpAnnouncementModal {...defaultProps} />);

    fireEvent.click(screen.getByRole("tab", { name: "Cursor" }));

    const snippet = document.querySelector(".mcp-announcement-code pre");
    expect(snippet).not.toBeNull();
    expect(snippet!.textContent).toContain('"mcpServers"');
    expect(snippet!.textContent).toContain(
      '"sponda": { "url": "https://sponda.capital/api/mcp/" }',
    );
  });

  it("switches to the Claude app tab and shows the endpoint URL", () => {
    render(<McpAnnouncementModal {...defaultProps} />);

    fireEvent.click(screen.getByRole("tab", { name: "Claude app" }));

    const snippet = document.querySelector(".mcp-announcement-code pre");
    expect(snippet).not.toBeNull();
    expect(snippet!.textContent).toBe("https://sponda.capital/api/mcp/");
  });

  it("renders the three example queries", () => {
    render(<McpAnnouncementModal {...defaultProps} />);

    const queries = document.querySelectorAll(".mcp-announcement-query");
    expect(queries).toHaveLength(3);
    expect(queries[1].textContent).toContain("WEGE3");
  });

  it("copies the active snippet to the clipboard", () => {
    render(<McpAnnouncementModal {...defaultProps} />);

    fireEvent.click(screen.getByRole("button", { name: "Copy" }));

    expect(clipboardWriteText).toHaveBeenCalledWith(
      CLAUDE_CODE_INSTALL_COMMAND,
    );
  });

  it("calls onClose from the close button", () => {
    const onClose = vi.fn();
    render(<McpAnnouncementModal onClose={onClose} />);

    fireEvent.click(screen.getByLabelText("Close"));

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('calls onClose from the "Maybe later" button', () => {
    const onClose = vi.fn();
    render(<McpAnnouncementModal onClose={onClose} />);

    fireEvent.click(screen.getByText("Maybe later"));

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("calls onClose when the backdrop is clicked, but not the panel", () => {
    const onClose = vi.fn();
    render(<McpAnnouncementModal onClose={onClose} />);

    fireEvent.click(document.querySelector(".mcp-announcement-panel")!);
    expect(onClose).not.toHaveBeenCalled();

    fireEvent.click(document.querySelector(".mcp-announcement-overlay")!);
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
