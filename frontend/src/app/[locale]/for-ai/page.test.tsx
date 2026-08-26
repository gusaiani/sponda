// @vitest-environment jsdom
import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { AI_ACCESS_SECTIONS, AI_ACCESS_TITLE } from "../../../lib/ai-access-copy";
import { AiAccessArticle } from "./AiAccessArticle";

afterEach(cleanup);

describe("AiAccessArticle", () => {
  it("renders the title as the page heading", () => {
    render(<AiAccessArticle />);
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(AI_ACCESS_TITLE);
  });

  it("renders every section", () => {
    render(<AiAccessArticle />);
    for (const section of AI_ACCESS_SECTIONS) {
      expect(screen.getByRole("heading", { name: section.heading })).toBeTruthy();
    }
  });

  it("renders fenced blocks as code, not as prose with backticks", () => {
    const { container } = render(<AiAccessArticle />);
    const code = container.querySelectorAll("pre");
    expect(code.length).toBeGreaterThan(0);
    expect(container.textContent).not.toContain("```");
  });

  it("names the MCP endpoint, which is the point of the page", () => {
    const { container } = render(<AiAccessArticle />);
    expect(container.textContent).toContain("https://sponda.capital/api/mcp");
  });

  it("is server-renderable, so a crawler sees the content in the HTML", () => {
    // No hooks, no client boundary. If this ever needs state, the content
    // stops being visible to the audience the page exists for.
    const source = AiAccessArticle.toString();
    expect(source).not.toContain("useState");
    expect(source).not.toContain("useEffect");
  });
});
