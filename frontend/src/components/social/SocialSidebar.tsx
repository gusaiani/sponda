"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useTranslation } from "../../i18n";
import { useAuth } from "../../hooks/useAuth";
import { useSocialFeed } from "../../hooks/useSocialFeed";
import { useSeenSponds } from "../../hooks/useSeenSponds";
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

  // Publish the rail's current width as a CSS variable so the rest of
  // the layout can adjust without React knowing. The breakpoint here
  // mirrors social-sidebar.css; below it the rail isn't rendered at all.
  useEffect(() => {
    if (typeof window === "undefined" || !hydrated) return;
    const root = document.documentElement;
    function publish() {
      const isDesktop = window.innerWidth > 1100;
      if (!isDesktop) {
        root.style.setProperty("--right-rail-width", "0px");
        return;
      }
      root.style.setProperty(
        "--right-rail-width",
        collapsed ? `${SIDEBAR_RAIL_WIDTH}px` : `${SIDEBAR_WIDTH}px`,
      );
    }
    publish();
    window.addEventListener("resize", publish);
    return () => {
      window.removeEventListener("resize", publish);
      root.style.setProperty("--right-rail-width", "0px");
    };
  }, [collapsed, hydrated]);

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

  // Always run the active tab's feed query — even when collapsed — so the
  // unread badge under the rail icon has data to count.
  const feedKind = isAuthenticated && tab === "following" ? "following" : "global";
  const feedQuery = useSocialFeed(feedKind);
  const { isSeen } = useSeenSponds();

  const unseenCount = useMemo(() => {
    const all = (feedQuery.data?.pages ?? []).flatMap((page) => page.results);
    let n = 0;
    for (const spond of all) {
      if (!isSeen(spond.id, spond.created_at)) n += 1;
      if (n > 99) return 100; // sentinel rendered as "99+"
    }
    return n;
  }, [feedQuery.data, isSeen]);

  if (!hydrated) return null;

  if (collapsed) {
    return (
      <button
        type="button"
        onClick={toggleCollapsed}
        aria-label={t("social.sidebar.expand")}
        title={t("social.sidebar.expand")}
        className="social-sidebar-rail"
        style={{
          position: "fixed",
          right: 0,
          top: HEADER_HEIGHT,
          bottom: 0,
          width: `${SIDEBAR_RAIL_WIDTH}px`,
          background: "#fafbfc",
          border: "none",
          borderTop: "1px solid #e1e4e8",
          borderLeft: "1px solid #e1e4e8",
          cursor: "pointer",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "flex-start",
          paddingTop: "14px",
          gap: "6px",
          zIndex: 20,
        }}
      >
        <SpeechBalloonIcon size={22} color="#1b347e" />
        {unseenCount > 0 && (
          <span
            aria-label={`${unseenCount} ${t("social.spond_noun_plural")}`}
            style={{
              fontSize: "11px",
              fontWeight: 700,
              color: "#1b347e",
              fontFamily: "'Inter', system-ui, sans-serif",
              lineHeight: 1,
            }}
          >
            {unseenCount > 99 ? "99+" : unseenCount}
          </span>
        )}
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
        borderTop: "1px solid #e1e4e8",
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
        <span style={{ display: "inline-flex", alignItems: "center", gap: "8px" }}>
          <SpeechBalloonIcon size={18} color="#1b347e" />
          <strong style={{ color: "#1b347e", fontSize: "15px" }}>
            {t("social.spond_noun_plural")}
          </strong>
        </span>
        <button
          type="button"
          onClick={toggleCollapsed}
          aria-label={t("social.sidebar.collapse")}
          title={t("social.sidebar.collapse")}
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
          <button
            role="tab"
            aria-selected={tab === "global"}
            onClick={() => selectTab("global")}
            style={tabStyle(tab === "global")}
          >
            {t("social.feed.tab_global")}
          </button>
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
        </div>

        <SpondFeed kind={isAuthenticated && tab === "following" ? "following" : "global"} />
      </div>
    </aside>
  );
}

/** Comic-book speech balloon — single recognizable affordance for Sponds. */
function SpeechBalloonIcon({ size = 20, color = "currentColor" }: { size?: number; color?: string }) {
  return (
    <svg
      aria-hidden
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke={color}
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {/* Rounded balloon */}
      <path d="M4 5h16a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-9l-5 4v-4H4a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2z" />
    </svg>
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
