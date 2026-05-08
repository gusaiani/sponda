"use client";

import { useState } from "react";
import Link from "next/link";
import { useTranslation } from "../../i18n";
import { useAuth } from "../../hooks/useAuth";
import { useDeleteSpond, useLikeSpond } from "../../hooks/useSocialFeed";
import type { SpondPayload } from "../../hooks/useProfile";
import { UserAvatar } from "./UserAvatar";

interface Props {
  spond: SpondPayload;
}

/**
 * Render plain Spond body with @handle and $TICKER tokens linkified.
 * Body is up to 500 chars and arrives plain-text, so a single regex pass
 * with split-and-stitch is fast enough — no DOM-walking, no DOMPurify.
 */
function renderBody(body: string, locale: string) {
  const parts: React.ReactNode[] = [];
  const re = /(@[a-z0-9_]{3,24}|\$[A-Z]{1,5}\d{0,2})\b/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let key = 0;

  while ((match = re.exec(body)) !== null) {
    if (match.index > lastIndex) {
      parts.push(body.slice(lastIndex, match.index));
    }
    const token = match[0];
    if (token.startsWith("@")) {
      const handle = token.slice(1);
      parts.push(
        <Link
          key={`m-${key++}`}
          href={`/${locale}/user/${handle}`}
          style={{ color: "#1b347e", fontWeight: 600 }}
        >
          {token}
        </Link>,
      );
    } else if (token.startsWith("$")) {
      const symbol = token.slice(1);
      parts.push(
        <Link
          key={`t-${key++}`}
          href={`/${locale}/${symbol}`}
          style={{ color: "#1b347e", fontWeight: 600 }}
        >
          {token}
        </Link>,
      );
    }
    lastIndex = re.lastIndex;
  }
  if (lastIndex < body.length) parts.push(body.slice(lastIndex));
  return parts;
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
  const [optimisticLiked, setOptimisticLiked] = useState<boolean | null>(null);
  const [optimisticLikeDelta, setOptimisticLikeDelta] = useState(0);

  const isMine = user?.handle && user.handle === spond.author.handle;
  const liked = optimisticLiked ?? spond.viewer_has_liked;
  const likeCount = spond.like_count + optimisticLikeDelta;

  function handleLikeToggle() {
    if (!user) return;
    const next = !liked;
    setOptimisticLiked(next);
    setOptimisticLikeDelta((prev) => prev + (next ? 1 : -1));
    likeSpond.mutate(
      { id: spond.id, like: next },
      {
        onError: () => {
          setOptimisticLiked((prev) => (prev === null ? null : !prev));
          setOptimisticLikeDelta((prev) => prev + (next ? -1 : 1));
        },
      },
    );
  }

  function handleDelete() {
    if (!isMine) return;
    if (!window.confirm(t("social.spond.confirm_delete"))) return;
    deleteSpond.mutate(spond.id);
  }

  return (
    <article style={cardStyle}>
      <div style={{ display: "flex", gap: "10px" }}>
        <Link href={`/${locale}/user/${spond.author.handle}`} aria-label={spond.author.display_name || spond.author.handle}>
          <UserAvatar handle={spond.author.handle} displayName={spond.author.display_name} size="md" />
        </Link>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: "8px" }}>
            <div>
              <Link
                href={`/${locale}/user/${spond.author.handle}`}
                style={{ color: "#222", fontWeight: 600, textDecoration: "none" }}
              >
                {spond.author.display_name || spond.author.handle}
              </Link>
              <span style={{ marginLeft: "6px", color: "#666", fontSize: "13px" }}>
                @{spond.author.handle}
              </span>
            </div>
            <Link
              href={`/${locale}/spond/${spond.id}`}
              style={{ color: "#888", fontSize: "13px", textDecoration: "none" }}
              title={new Date(spond.created_at).toLocaleString(locale)}
            >
              {relativeTime(spond.created_at, locale)}
            </Link>
          </div>
          <div style={{ marginTop: "4px", whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
            {renderBody(spond.body, locale)}
          </div>
          {spond.ticker && (
            <div style={{ marginTop: "6px" }}>
              <Link
                href={`/${locale}/${spond.ticker}`}
                style={{
                  display: "inline-block", padding: "2px 8px",
                  borderRadius: "999px", background: "#eef1ff",
                  color: "#1b347e", fontWeight: 600, fontSize: "12px",
                  textDecoration: "none",
                }}
              >
                ${spond.ticker}
              </Link>
            </div>
          )}
          <div style={{ display: "flex", gap: "16px", marginTop: "10px", color: "#555", fontSize: "13px" }}>
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
                fontSize: "13px",
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
                  cursor: "pointer", color: "#a00", fontSize: "13px",
                }}
              >
                {t("social.spond.delete")}
              </button>
            )}
          </div>
        </div>
      </div>
    </article>
  );
}

const cardStyle: React.CSSProperties = {
  padding: "12px",
  border: "1px solid #e1e4e8",
  borderRadius: "10px",
  background: "#ffffff",
  marginBottom: "10px",
};
