// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { McpAnnouncementModal } from "./McpAnnouncementModal";
import { LanguageProvider } from "../i18n/LanguageContext";
import { pt } from "../i18n/locales/pt";
import { en } from "../i18n/locales/en";
import { es } from "../i18n/locales/es";
import { zh } from "../i18n/locales/zh";
import { fr } from "../i18n/locales/fr";
import { de } from "../i18n/locales/de";
import { it as italian } from "../i18n/locales/it";
import type { Locale, TranslationDictionary } from "../i18n/types";

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

  it("links the Claude app breadcrumb to the prefilled install dialog", () => {
    render(<McpAnnouncementModal {...defaultProps} />);

    fireEvent.click(screen.getByRole("tab", { name: "Claude app" }));

    // claude.ai's official install-link format: opens Customize › Connectors
    // with the Add custom connector dialog prefilled (docs: connectors/building).
    const link = document.querySelector<HTMLAnchorElement>(
      ".mcp-announcement-hint a",
    );
    expect(link).not.toBeNull();
    expect(link!.href).toBe(
      "https://claude.ai/customize/connectors?modal=add-custom-connector" +
        "&connectorName=Sponda" +
        "&connectorUrl=https%3A%2F%2Fsponda.capital%2Fapi%2Fmcp%2F",
    );
    expect(link!.target).toBe("_blank");
    expect(link!.rel).toContain("noreferrer");
    // claude.ai moved connectors from Settings to Customize.
    expect(link!.textContent).toContain("Customize › Connectors");
    const hint = document.querySelector(".mcp-announcement-hint");
    expect(hint!.textContent).toContain("then paste:");
  });

  it("switches to the ChatGPT tab and shows the endpoint URL", () => {
    render(<McpAnnouncementModal {...defaultProps} />);

    fireEvent.click(screen.getByRole("tab", { name: "ChatGPT" }));

    const snippet = document.querySelector(".mcp-announcement-code pre");
    expect(snippet).not.toBeNull();
    expect(snippet!.textContent).toBe("https://sponda.capital/api/mcp/");
    const hint = document.querySelector(".mcp-announcement-hint");
    expect(hint!.textContent).toContain("Developer mode");
  });

  it("links the ChatGPT breadcrumb to the connectors settings page", () => {
    render(<McpAnnouncementModal {...defaultProps} />);

    fireEvent.click(screen.getByRole("tab", { name: "ChatGPT" }));

    const link = document.querySelector<HTMLAnchorElement>(
      ".mcp-announcement-hint a",
    );
    expect(link).not.toBeNull();
    expect(link!.href).toBe("https://chatgpt.com/#settings/Connectors");
    expect(link!.target).toBe("_blank");
    expect(link!.textContent).toContain("Settings › Connectors");
  });

  it("renders no link in the hint for terminal-based installs", () => {
    render(<McpAnnouncementModal {...defaultProps} />);

    expect(document.querySelector(".mcp-announcement-hint a")).toBeNull();
  });

  it("renders the three example queries with US companies in English", () => {
    render(<McpAnnouncementModal {...defaultProps} />);

    const queries = document.querySelectorAll(".mcp-announcement-query");
    expect(queries).toHaveLength(3);
    expect(queries[0].textContent).toContain("US companies");
    expect(queries[1].textContent).toContain("AAPL");
  });

  it("renders Brazilian example queries in Portuguese", () => {
    render(
      <LanguageProvider initialLocale="pt">
        <McpAnnouncementModal {...defaultProps} />
      </LanguageProvider>,
    );

    const queries = document.querySelectorAll(".mcp-announcement-query");
    expect(queries[0].textContent).toContain("brasileiras");
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

describe("MCP example queries are localized per country", () => {
  // Each locale anchors its examples on a flagship company from that
  // country that resolves in Sponda (verified against the live MCP server).
  const FLAGSHIP_TICKER_BY_LOCALE: Record<Locale, string> = {
    en: "AAPL", // Apple — US
    pt: "WEGE3", // WEG — Brazil
    es: "SAN", // Banco Santander — Spain
    fr: "LVMUY", // LVMH — France
    de: "SAP", // SAP — Germany
    it: "RACE", // Ferrari — Italy
    zh: "BABA", // Alibaba — China
  };

  const DICTIONARIES: Record<Locale, TranslationDictionary> = {
    en,
    pt,
    es,
    fr,
    de,
    it: italian,
    zh,
  };

  for (const [locale, ticker] of Object.entries(FLAGSHIP_TICKER_BY_LOCALE)) {
    it(`${locale} company query features ${ticker}`, () => {
      const dictionary = DICTIONARIES[locale as Locale];
      expect(dictionary["mcp.query_company"]).toContain(ticker);
    });
  }

  it("no locale points its screener example at another locale's market", () => {
    // The pre-localization copy screened Brazil from every language.
    expect(en["mcp.query_screener"]).not.toMatch(/Brazilian/);
    expect(es["mcp.query_screener"]).not.toMatch(/brasileñas/);
    expect(fr["mcp.query_screener"]).not.toMatch(/brésiliennes/);
    expect(de["mcp.query_screener"]).not.toMatch(/brasilianischen/);
    expect(italian["mcp.query_screener"]).not.toMatch(/brasiliane/);
    expect(zh["mcp.query_screener"]).not.toMatch(/巴西/);
  });
});
