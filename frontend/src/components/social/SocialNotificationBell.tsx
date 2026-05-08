"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useTranslation } from "../../i18n";
import { useAuth } from "../../hooks/useAuth";
import {
  useMarkNotificationsRead,
  useSocialNotifications,
  type SocialNotification,
} from "../../hooks/useSocialNotifications";
import { useFollowRequestAction } from "../../hooks/useFollow";
import { UserAvatar } from "./UserAvatar";

export function SocialNotificationBell() {
  const { t, locale } = useTranslation();
  const { isAuthenticated } = useAuth();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const { data } = useSocialNotifications(isAuthenticated);
  const markRead = useMarkNotificationsRead();
  const requestAction = useFollowRequestAction();

  useEffect(() => {
    function clickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", clickOutside);
    return () => document.removeEventListener("mousedown", clickOutside);
  }, []);

  if (!isAuthenticated) return null;

  const unread = data?.unread_count ?? 0;
  const items = data?.notifications ?? [];

  function handleOpen() {
    setOpen((prev) => !prev);
  }

  function notificationLabel(n: SocialNotification) {
    const actor = n.actor?.display_name || (n.actor?.handle ? `@${n.actor.handle}` : "");
    if (n.verb === "followed") return t("social.notifications.followed", { actor });
    if (n.verb === "follow_requested") return t("social.notifications.follow_requested", { actor });
    if (n.verb === "replied") return t("social.notifications.replied", { actor });
    if (n.verb === "mentioned") return t("social.notifications.mentioned", { actor });
    if (n.verb === "liked") return t("social.notifications.liked", { actor });
    return n.verb;
  }

  function targetHref(n: SocialNotification): string | null {
    if (!n.target_id) return null;
    if (n.target_type === "spond") return `/${locale}/spond/${n.target_id}`;
    if (n.target_type === "follow" && n.actor) return `/${locale}/user/${n.actor.handle}`;
    return null;
  }

  return (
    <div ref={ref} style={{ position: "relative", display: "inline-block" }}>
      <button
        type="button"
        onClick={handleOpen}
        aria-label={t("social.notifications.title")}
        style={{
          background: "none", border: "none", cursor: "pointer",
          padding: "6px", position: "relative",
        }}
      >
        <span aria-hidden style={{ fontSize: "16px" }}>📨</span>
        {unread > 0 && (
          <span
            aria-label={t("social.notifications.unread_count", { count: String(unread) })}
            style={{
              position: "absolute", top: 0, right: 0,
              minWidth: "16px", height: "16px",
              padding: "0 4px",
              borderRadius: "999px",
              background: "#a13a4a", color: "#fff",
              fontSize: "10px", fontWeight: 700,
              display: "flex", alignItems: "center", justifyContent: "center",
            }}
          >
            {unread > 99 ? "99+" : unread}
          </span>
        )}
      </button>
      {open && (
        <div
          role="dialog"
          aria-label={t("social.notifications.title")}
          style={{
            position: "absolute", right: 0, top: "100%", marginTop: "4px",
            width: "320px", maxHeight: "400px", overflowY: "auto",
            background: "#fff", border: "1px solid #e1e4e8",
            borderRadius: "8px", boxShadow: "0 6px 16px rgba(0,0,0,0.1)",
            zIndex: 100,
          }}
        >
          <div style={{ padding: "8px 12px", borderBottom: "1px solid #f0f0f0", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <strong>{t("social.notifications.title")}</strong>
            {unread > 0 && (
              <button
                type="button"
                onClick={() => markRead.mutate(undefined)}
                style={{ background: "none", border: "none", color: "#1b347e", cursor: "pointer", fontSize: "12px" }}
              >
                {t("social.notifications.mark_all_read")}
              </button>
            )}
          </div>
          {items.length === 0 ? (
            <div style={{ padding: "16px", color: "#666", textAlign: "center" }}>
              {t("social.notifications.empty")}
            </div>
          ) : (
            items.map((n) => {
              const href = targetHref(n);
              const Inner = (
                <div
                  style={{
                    padding: "10px 12px",
                    borderBottom: "1px solid #f0f0f0",
                    background: n.read_at ? "#fff" : "#f6f8ff",
                    display: "flex", gap: "8px", alignItems: "flex-start",
                  }}
                >
                  {n.actor && (
                    <UserAvatar handle={n.actor.handle} displayName={n.actor.display_name} size="sm" />
                  )}
                  <div style={{ flex: 1, minWidth: 0, fontSize: "13px" }}>
                    <div>{notificationLabel(n)}</div>
                    {n.verb === "follow_requested" && (
                      <div style={{ display: "flex", gap: "8px", marginTop: "6px" }}>
                        <button
                          type="button"
                          onClick={() => requestAction.mutate({ id: Number(n.target_id), action: "accept" })}
                          style={{ padding: "2px 8px", border: "none", borderRadius: "4px", background: "#1b347e", color: "#fff", fontSize: "12px", cursor: "pointer" }}
                        >
                          {t("social.notifications.accept")}
                        </button>
                        <button
                          type="button"
                          onClick={() => requestAction.mutate({ id: Number(n.target_id), action: "reject" })}
                          style={{ padding: "2px 8px", border: "1px solid #ccc", borderRadius: "4px", background: "#fff", fontSize: "12px", cursor: "pointer" }}
                        >
                          {t("social.notifications.reject")}
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              );
              return href ? (
                <Link
                  key={n.id}
                  href={href}
                  onClick={() => setOpen(false)}
                  style={{ textDecoration: "none", color: "inherit", display: "block" }}
                >
                  {Inner}
                </Link>
              ) : (
                <div key={n.id}>{Inner}</div>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
