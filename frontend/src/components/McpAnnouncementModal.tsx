"use client";

import { useState } from "react";
import { useTranslation } from "../i18n";
import type { TranslationKey } from "../i18n";
import "../styles/mcp-announcement.css";

export const MCP_ENDPOINT_URL = "https://sponda.capital/api/mcp/";

const CLAUDE_CODE_INSTALL_COMMAND = `claude mcp add --transport http sponda ${MCP_ENDPOINT_URL}`;

const CURSOR_CONFIG_SNIPPET = `{
  "mcpServers": {
    "sponda": { "url": "${MCP_ENDPOINT_URL}" }
  }
}`;

type McpInstallTargetId = "claude-code" | "cursor" | "claude-app" | "chatgpt";

interface McpInstallTarget {
  id: McpInstallTargetId;
  hintKey: TranslationKey;
  snippet: string;
}

const INSTALL_TARGETS: McpInstallTarget[] = [
  {
    id: "claude-code",
    hintKey: "mcp.hint_claude_code",
    snippet: CLAUDE_CODE_INSTALL_COMMAND,
  },
  {
    id: "cursor",
    hintKey: "mcp.hint_cursor",
    snippet: CURSOR_CONFIG_SNIPPET,
  },
  {
    id: "claude-app",
    hintKey: "mcp.hint_claude_app",
    snippet: MCP_ENDPOINT_URL,
  },
  {
    id: "chatgpt",
    hintKey: "mcp.hint_chatgpt",
    snippet: MCP_ENDPOINT_URL,
  },
];

const COPY_FEEDBACK_DURATION_MS = 1500;

const EXAMPLE_QUERY_KEYS: TranslationKey[] = [
  "mcp.query_screener",
  "mcp.query_company",
  "mcp.query_ranking",
];

interface McpAnnouncementModalProps {
  onClose: () => void;
}

export function McpAnnouncementModal({ onClose }: McpAnnouncementModalProps) {
  const { t } = useTranslation();
  const [activeTargetId, setActiveTargetId] =
    useState<McpInstallTargetId>("claude-code");
  const activeTarget = INSTALL_TARGETS.find(
    (target) => target.id === activeTargetId,
  )!;

  function installTargetLabel(targetId: McpInstallTargetId): string {
    if (targetId === "claude-code") return "Claude Code";
    if (targetId === "cursor") return "Cursor";
    if (targetId === "chatgpt") return "ChatGPT";
    return t("mcp.tab_claude_app");
  }

  return (
    <div className="mcp-announcement-overlay" onClick={onClose}>
      <div
        className="mcp-announcement-panel"
        role="dialog"
        aria-labelledby="mcp-announcement-title"
        onClick={(event) => event.stopPropagation()}
      >
        <button
          type="button"
          className="mcp-announcement-close"
          aria-label={t("common.close")}
          onClick={onClose}
        >
          ×
        </button>

        <span className="mcp-announcement-eyebrow">{t("mcp.eyebrow")}</span>
        <h2 id="mcp-announcement-title" className="mcp-announcement-title">
          {t("mcp.title")}
        </h2>
        <p className="mcp-announcement-subtitle">{t("mcp.subtitle")}</p>

        <div className="mcp-announcement-section-label">
          {t("mcp.install_label")}
        </div>
        <div className="mcp-announcement-tabs" role="tablist">
          {INSTALL_TARGETS.map((target) => (
            <button
              key={target.id}
              type="button"
              role="tab"
              aria-selected={target.id === activeTargetId}
              className={
                target.id === activeTargetId
                  ? "mcp-announcement-tab mcp-announcement-tab-active"
                  : "mcp-announcement-tab"
              }
              onClick={() => setActiveTargetId(target.id)}
            >
              {installTargetLabel(target.id)}
            </button>
          ))}
        </div>
        <p className="mcp-announcement-hint">{t(activeTarget.hintKey)}</p>
        <div className="mcp-announcement-code">
          <pre>{activeTarget.snippet}</pre>
          <CopySnippetButton snippet={activeTarget.snippet} />
        </div>

        <div className="mcp-announcement-section-label">
          {t("mcp.try_asking")}
        </div>
        <div className="mcp-announcement-queries">
          {EXAMPLE_QUERY_KEYS.map((queryKey) => (
            <div key={queryKey} className="mcp-announcement-query">
              <span className="mcp-announcement-query-prompt">›</span>
              {t(queryKey)}
            </div>
          ))}
        </div>

        <div className="mcp-announcement-footer">
          <span className="mcp-announcement-meta">{t("mcp.meta")}</span>
          <button
            type="button"
            className="mcp-announcement-later"
            onClick={onClose}
          >
            {t("mcp.maybe_later")}
          </button>
        </div>
      </div>
    </div>
  );
}

function CopySnippetButton({ snippet }: { snippet: string }) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);

  function handleCopy() {
    navigator.clipboard.writeText(snippet);
    setCopied(true);
    setTimeout(() => setCopied(false), COPY_FEEDBACK_DURATION_MS);
  }

  return (
    <button
      type="button"
      className="mcp-announcement-copy"
      onClick={handleCopy}
    >
      {copied ? t("mcp.copied") : t("mcp.copy")}
    </button>
  );
}
