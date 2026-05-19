"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "../../i18n";
import type { SpondPayload } from "../../hooks/useProfile";
import { SpondCard } from "./SpondCard";
import { SpondComposer } from "./SpondComposer";

interface ThreadResponse {
  spond: SpondPayload;
  replies: SpondPayload[];
}

interface Props {
  spond: SpondPayload;
  /** Replies already loaded (Spond permalink page). When provided they
   *  render immediately and the lazy "show replies" toggle is skipped. */
  replies?: SpondPayload[];
  /** When true, the root "Responder" toggles an inline composer inside
   *  this box instead of linking to the permalink (Spond page). */
  inlineReply?: boolean;
  /** Refresh callback after a reply is posted (page refetch). */
  onChanged?: () => void;
}

async function fetchThread(id: string): Promise<ThreadResponse> {
  const response = await fetch(`/api/social/sponds/${id}/`, { credentials: "include" });
  if (!response.ok) throw new Error("thread_fetch_failed");
  return response.json();
}

/**
 * A Spond and its replies grouped in a single box. The replies are nested
 * beneath the root with a left rail so the thread reads as one unit.
 *
 * Two modes:
 *  - Eager (`replies` provided, e.g. the permalink page): replies render
 *    immediately; the root's "Responder" toggles an inline composer.
 *  - Lazy (feed/sidebar): only the root and a "show replies" toggle show;
 *    the thread is fetched on demand and nested in the same box.
 */
export function SpondThread({ spond, replies, inlineReply, onChanged }: Props) {
  const { t } = useTranslation();
  const [replying, setReplying] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const eager = replies !== undefined;

  const lazyQuery = useQuery({
    queryKey: ["social-thread", spond.id],
    queryFn: () => fetchThread(spond.id),
    enabled: !eager && expanded,
    staleTime: 5_000,
  });

  const shownReplies = eager ? replies! : (lazyQuery.data?.replies ?? []);
  const hasReplies = spond.reply_count > 0 || shownReplies.length > 0;

  return (
    <article style={boxStyle}>
      <SpondCard
        spond={spond}
        embedded
        {...(inlineReply
          ? { onReplyClick: () => setReplying((open) => !open), replyActive: replying }
          : {})}
      />

      {inlineReply && replying && (
        <div style={composerWrapStyle}>
          <SpondComposer
            inline
            parentId={spond.id}
            parentHandle={spond.author.handle}
            onSubmitted={() => {
              setReplying(false);
              onChanged?.();
            }}
          />
        </div>
      )}

      {!eager && hasReplies && (
        <button
          type="button"
          onClick={() => setExpanded((open) => !open)}
          style={toggleStyle}
        >
          {expanded
            ? t("social.spond.hide_replies")
            : t("social.spond.show_replies", { count: String(spond.reply_count) })}
        </button>
      )}

      {!eager && expanded && lazyQuery.isLoading && (
        <div style={loadingStyle}>{t("common.loading")}</div>
      )}

      {(eager ? shownReplies.length > 0 : expanded && shownReplies.length > 0) && (
        <div style={repliesStyle}>
          {shownReplies.map((reply, index) => (
            <div key={reply.id} style={index > 0 ? replyRowStyle : undefined}>
              <SpondCard spond={reply} embedded />
            </div>
          ))}
        </div>
      )}
    </article>
  );
}

const boxStyle: React.CSSProperties = {
  border: "1px solid #e1e4e8",
  borderRadius: "8px",
  background: "#ffffff",
  marginBottom: "8px",
  overflow: "hidden",
};

const composerWrapStyle: React.CSSProperties = {
  borderTop: "1px solid #eef0f2",
};

const toggleStyle: React.CSSProperties = {
  display: "block",
  width: "100%",
  textAlign: "left",
  padding: "8px 12px",
  background: "#f6f8fa",
  border: "none",
  borderTop: "1px solid #eef0f2",
  color: "#1b347e",
  fontWeight: 600,
  fontSize: "12px",
  cursor: "pointer",
};

const loadingStyle: React.CSSProperties = {
  padding: "10px 12px",
  color: "#666",
  fontSize: "12px",
};

const repliesStyle: React.CSSProperties = {
  borderTop: "1px solid #eef0f2",
  paddingLeft: "12px",
  borderLeft: "2px solid #e1e4e8",
};

const replyRowStyle: React.CSSProperties = {
  borderTop: "1px solid #f0f2f4",
};
