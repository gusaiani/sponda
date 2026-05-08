"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useTranslation } from "../../i18n";
import { useAuth } from "../../hooks/useAuth";
import { SpondComposer } from "./SpondComposer";
import { SpondFeed } from "./SpondFeed";

const STORAGE_KEY = "sponda-social-feed-tab";

type Tab = "following" | "global";

export function SocialHomeSection() {
  const { t, locale } = useTranslation();
  const { isAuthenticated } = useAuth();
  const [tab, setTab] = useState<Tab>("global");

  useEffect(() => {
    if (typeof window === "undefined") return;
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored === "following" || stored === "global") setTab(stored);
  }, []);

  function selectTab(next: Tab) {
    setTab(next);
    if (typeof window !== "undefined") window.localStorage.setItem(STORAGE_KEY, next);
  }

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
