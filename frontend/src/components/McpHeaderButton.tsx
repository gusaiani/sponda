"use client";

import { useTranslation } from "../i18n";
import "../styles/mcp-announcement.css";

interface McpHeaderButtonProps {
  onClick: () => void;
}

/** Header pill next to the Screener link that reopens the MCP announcement. */
export function McpHeaderButton({ onClick }: McpHeaderButtonProps) {
  const { t } = useTranslation();
  return (
    <button
      type="button"
      className="app-header-mcp-link"
      onClick={onClick}
      title={t("mcp.header_button_title")}
    >
      MCP
      <span className="app-header-mcp-new-badge">{t("mcp.eyebrow")}</span>
    </button>
  );
}
