"use client";

import Link from "next/link";
import { useTranslation } from "../../i18n";
import { useStoredState } from "../../hooks/useStoredState";
import { useAuth } from "../../hooks/useAuth";
import { SpondComposer } from "./SpondComposer";
import { SpondFeed } from "./SpondFeed";

const STORAGE_KEY = "sponda-social-feed-tab";

type Tab = "following" | "global";

/** Server render, and anyone with no stored choice, sees the global feed. */
const DEFAULT_TAB: Tab = "global";

const parseTab = (raw: string | null): Tab =>
  raw === "following" || raw === "global" ? raw : DEFAULT_TAB;
const serializeTab = (tab: Tab): string => tab;

export function SocialHomeSection() {
  const { t, locale } = useTranslation();
  const { isAuthenticated } = useAuth();
  // Shares STORAGE_KEY with SocialSidebar, so the two now agree on the active
  // tab within a session instead of drifting until the next page load.
  const [tab, selectTab] = useStoredState<Tab>(
    STORAGE_KEY, DEFAULT_TAB, parseTab, serializeTab,
  );

  return (
    <section
      aria-label={t("social.spond_noun_plural")}
      style={{
        maxWidth: "640px", margin: "32px auto", padding: "0 16px",
      }}
    >
      <SpondComposer />

      <div role="tablist" aria-label={t("social.spond_noun_plural")} style={tabRowStyle}>
        {isAuthenticated ? (
          <button
            role="tab"
            aria-selected={tab === "following"}
            onClick={() => selectTab("following")}
            style={tabStyle(tab === "following")}
          >
            {t("social.feed.tab_following")}
          </button>
        ) : (
          <Link
            href={`/${locale}/login`}
            style={{ ...tabStyle(false), textDecoration: "none" }}
          >
            {t("social.feed.login_to_follow")}
          </Link>
        )}
        <button
          role="tab"
          aria-selected={tab === "global"}
          onClick={() => selectTab("global")}
          style={tabStyle(tab === "global")}
        >
          {t("social.feed.tab_global")}
        </button>
      </div>

      <SpondFeed kind={isAuthenticated && tab === "following" ? "following" : "global"} />
    </section>
  );
}

const tabRowStyle: React.CSSProperties = {
  display: "flex",
  borderBottom: "1px solid #e1e4e8",
  marginBottom: "12px",
  gap: "4px",
};

function tabStyle(active: boolean): React.CSSProperties {
  return {
    padding: "8px 14px",
    border: "none",
    borderBottom: active ? "2px solid #1b347e" : "2px solid transparent",
    background: "none",
    color: active ? "#1b347e" : "#666",
    fontWeight: active ? 600 : 400,
    cursor: "pointer",
    fontSize: "14px",
  };
}
