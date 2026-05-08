"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useTranslation } from "../../i18n";
import { useAuth } from "../../hooks/useAuth";
import { SpondComposer } from "./SpondComposer";
import { SpondFeed } from "./SpondFeed";

const COLLAPSED_KEY = "sponda-social-sidebar-collapsed";
const TAB_KEY = "sponda-social-feed-tab";
const SIDEBAR_WIDTH = 380;
const SIDEBAR_RAIL_WIDTH = 36;
const HEADER_HEIGHT = 60;

type Tab = "following" | "global";

/**
 * YouTube-style collapsible right column. Visible on desktop only — below
 * the breakpoint we hide it entirely so the centered main content keeps the
 * full viewport. Collapsed state persists across reloads.
 */
export function SocialSidebar() {
  const { t, locale } = useTranslation();
  const { isAuthenticated } = useAuth();
  const [collapsed, setCollapsed] = useState(false);
  const [tab, setTab] = useState<Tab>("global");
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const stored = window.localStorage.getItem(COLLAPSED_KEY);
    if (stored === "1") setCollapsed(true);
    const storedTab = window.localStorage.getItem(TAB_KEY);
    if (storedTab === "following" || storedTab === "global") setTab(storedTab);
    setHydrated(true);
  }, []);

  function toggleCollapsed() {
    setCollapsed((prev) => {
      const next = !prev;
      if (typeof window !== "undefined") {
        window.localStorage.setItem(COLLAPSED_KEY, next ? "1" : "0");
      }
      return next;
    });
  }

  function selectTab(next: Tab) {
    setTab(next);
    if (typeof window !== "undefined") window.localStorage.setItem(TAB_KEY, next);
  }

  if (!hydrated) return null;

  if (collapsed) {
    return (
      <button
        type="button"
        onClick={toggleCollapsed}
        aria-label={t("social.sidebar.expand")}
        className="social-sidebar-rail"
        style={{
          position: "fixed",
          right: 0,
          top: HEADER_HEIGHT,
          bottom: 0,
          width: `${SIDEBAR_RAIL_WIDTH}px`,
          background: "#fafbfc",
          border: "none",
          borderLeft: "1px solid #e1e4e8",
          cursor: "pointer",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "flex-start",
          paddingTop: "16px",
          gap: "12px",
          zIndex: 20,
        }}
      >
        <span aria-hidden style={{ fontSize: "16px", color: "#1b347e" }}>‹</span>
        <span
          style={{
            writingMode: "vertical-rl",
            transform: "rotate(180deg)",
            color: "#1b347e",
            fontWeight: 600,
            fontSize: "13px",
            letterSpacing: "1px",
          }}
        >
          {t("social.spond_noun_plural")}
        </span>
      </button>
    );
  }

  return (
    <aside
      aria-label={t("social.spond_noun_plural")}
      className="social-sidebar"
      style={{
        position: "fixed",
        right: 0,
        top: HEADER_HEIGHT,
        bottom: 0,
        width: `${SIDEBAR_WIDTH}px`,
        background: "#ffffff",
        borderLeft: "1px solid #e1e4e8",
        display: "flex",
        flexDirection: "column",
        zIndex: 20,
      }}
    >
      <div
        style={{
          padding: "10px 14px",
          borderBottom: "1px solid #e1e4e8",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          background: "#fafbfc",
        }}
      >
        <strong style={{ color: "#1b347e", fontSize: "15px" }}>
          {t("social.spond_noun_plural")}
        </strong>
        <button
          type="button"
          onClick={toggleCollapsed}
          aria-label={t("social.sidebar.collapse")}
          style={{
            background: "none",
            border: "none",
            cursor: "pointer",
            padding: "4px 8px",
            color: "#666",
            fontSize: "16px",
          }}
        >
          ›
        </button>
      </div>

      <div style={{ overflowY: "auto", flex: 1, padding: "12px" }}>
        <SpondComposer />

        <div
          role="tablist"
          aria-label={t("social.spond_noun_plural")}
          style={{
            display: "flex",
            borderBottom: "1px solid #e1e4e8",
            marginBottom: "10px",
            gap: "4px",
          }}
        >
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
      </div>
    </aside>
  );
}

function tabStyle(active: boolean): React.CSSProperties {
  return {
    padding: "6px 12px",
    border: "none",
    borderBottom: active ? "2px solid #1b347e" : "2px solid transparent",
    background: "none",
    color: active ? "#1b347e" : "#666",
    fontWeight: active ? 600 : 400,
    cursor: "pointer",
    fontSize: "13px",
  };
}
