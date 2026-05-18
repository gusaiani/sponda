"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useTranslation } from "../../i18n";
import { useAuth } from "../../hooks/useAuth";
import { useDeleteSpond, useLikeSpond } from "../../hooks/useSocialFeed";
import { useSeenSponds } from "../../hooks/useSeenSponds";
import type { SpondPayload } from "../../hooks/useProfile";
import { useEmailVerification } from "../EmailVerificationGate";
import { UserAvatar } from "./UserAvatar";
import { renderSpondBody } from "./renderSpondBody";

interface Props {
  spond: SpondPayload;
}

function relativeTime(iso: string, locale: string): string {
  const then = new Date(iso).getTime();
  const now = Date.now();
  const diffSec = Math.max(0, Math.round((now - then) / 1000));
  if (diffSec < 60) return `${diffSec}s`;
  const diffMin = Math.round(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m`;
  const diffHour = Math.round(diffMin / 60);
  if (diffHour < 24) return `${diffHour}h`;
  const diffDay = Math.round(diffHour / 24);
  if (diffDay < 30) return `${diffDay}d`;
  return new Date(iso).toLocaleDateString(locale);
}

export function SpondCard({ spond }: Props) {
  const { t, locale } = useTranslation();
  const { user } = useAuth();
  const likeSpond = useLikeSpond();
  const deleteSpond = useDeleteSpond();
  const { requireVerification } = useEmailVerification();
  // Single piece of optimistic state — the user's *intended* like state.
  // The displayed count is derived from this plus the server's baseline.
  // When the server catches up (refetch matches our intent), the diff
  // collapses to zero automatically — no separate delta to reset.
  const [optimisticLiked, setOptimisticLiked] = useState<boolean | null>(null);

  const isMine = user?.handle && user.handle === spond.author.handle;
  const liked = optimisticLiked ?? spond.viewer_has_liked;
  const likeCount = spond.like_count + (
    optimisticLiked !== null && optimisticLiked !== spond.viewer_has_liked
      ? (optimisticLiked ? 1 : -1)
      : 0
  );

  function handleLikeToggle() {
    if (!user) return;
    const next = !liked;
    // Optimistic UI runs immediately so the click feels responsive even
    // when verification is pending. The actual mutation only fires once
    // the user is verified — requireVerification replays it then.
    setOptimisticLiked(next);
    requireVerification(() => {
      likeSpond.mutate(
        { id: spond.id, like: next },
        {
          onError: () => {
            // Roll back the optimistic toggle.
            setOptimisticLiked(null);
          },
        },
      );
    });
  }

  function handleDelete() {
    if (!isMine) return;
    if (!window.confirm(t("social.spond.confirm_delete"))) return;
    deleteSpond.mutate(spond.id);
  }

  // Mark this Spond as "seen" when it scrolls into view. The collapsed
  // sidebar's unread badge counts younger-than-48h Sponds the user
  // hasn't yet observed; once they scroll past, it stops counting.
  const articleRef = useRef<HTMLElement>(null);
  const { markSeen } = useSeenSponds();
  useEffect(() => {
    const node = articleRef.current;
    if (!node || typeof window === "undefined" || !("IntersectionObserver" in window)) {
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            markSeen(spond.id);
            observer.disconnect();
            break;
          }
        }
      },
      { threshold: 0.5 },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [spond.id, markSeen]);

  return (
    <article ref={articleRef} style={cardStyle}>
      {/* Inline header: avatar + display name + handle + timestamp on one
        * line. Body wraps the full card width below. Tighter than the
        * prior layout — saves ~36px of horizontal gutter, a lot in the
        * narrow right rail. */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "6px", minWidth: 0, flex: 1 }}>
          <Link
            href={`/${locale}/user/${spond.author.handle}`}
            aria-label={spond.author.display_name || spond.author.handle}
            style={{ flexShrink: 0, display: "inline-flex" }}
          >
            <UserAvatar handle={spond.author.handle} displayName={spond.author.display_name} size="sm" />
          </Link>
          <Link
            href={`/${locale}/user/${spond.author.handle}`}
            style={{ color: "#222", fontWeight: 600, fontSize: "13px", textDecoration: "none", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}
          >
            {spond.author.display_name || spond.author.handle}
          </Link>
          <Link
            href={`/${locale}/user/${spond.author.handle}`}
            style={{ color: "#888", fontSize: "12px", whiteSpace: "nowrap", textDecoration: "none" }}
          >
            @{spond.author.handle}
          </Link>
        </div>
        <Link
          href={`/${locale}/spond/${spond.id}`}
          style={{ color: "#888", fontSize: "12px", textDecoration: "none", flexShrink: 0 }}
          title={new Date(spond.created_at).toLocaleString(locale)}
        >
          {relativeTime(spond.created_at, locale)}
        </Link>
      </div>
      <div style={{ fontSize: "13px", lineHeight: 1.45, whiteSpace: "pre-wrap", wordBreak: "break-word", color: "#222" }}>
        {renderSpondBody(spond.body, locale)}
      </div>
      {spond.ticker && (
        <div style={{ marginTop: "6px" }}>
          <Link
            href={`/${locale}/${spond.ticker}`}
            style={{
              display: "inline-block", padding: "1px 7px",
              borderRadius: "999px", background: "#eef1ff",
              color: "#1b347e", fontWeight: 600, fontSize: "11px",
              textDecoration: "none",
            }}
          >
            ${spond.ticker}
          </Link>
        </div>
      )}
      <div style={{ display: "flex", gap: "14px", marginTop: "8px", color: "#666", fontSize: "12px" }}>
        <Link href={`/${locale}/spond/${spond.id}`} style={{ color: "inherit", textDecoration: "none" }}>
          {t("social.spond.reply")} {spond.reply_count > 0 && `· ${spond.reply_count}`}
        </Link>
        <button
          type="button"
          onClick={handleLikeToggle}
          disabled={!user}
          style={{
            background: "none", border: "none", padding: 0,
            cursor: user ? "pointer" : "default",
            color: liked ? "#a13a4a" : "inherit",
            fontWeight: liked ? 600 : 400,
            fontSize: "12px",
          }}
        >
          {liked ? t("social.spond.unlike") : t("social.spond.like")}{likeCount > 0 && ` · ${likeCount}`}
        </button>
        {isMine && (
          <button
            type="button"
            onClick={handleDelete}
            style={{
              background: "none", border: "none", padding: 0,
              cursor: "pointer", color: "#a00", fontSize: "12px",
            }}
          >
            {t("social.spond.delete")}
          </button>
        )}
      </div>
    </article>
  );
}

const cardStyle: React.CSSProperties = {
  padding: "10px 12px",
  border: "1px solid #e1e4e8",
  borderRadius: "8px",
  background: "#ffffff",
  marginBottom: "8px",
};
