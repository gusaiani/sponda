"use client";

import { useState } from "react";
import { useTranslation } from "../../i18n";
import { useAuth } from "../../hooks/useAuth";
import { useCreateSpond } from "../../hooks/useSocialFeed";
import { useEmailVerification } from "../EmailVerificationGate";
import { UserAvatar } from "./UserAvatar";

const SPOND_MAX_LENGTH = 500;

interface Props {
  /** When set, the composer is locked to this ticker (used on company pages). */
  lockedTicker?: string;
  /** When set, this composer creates a reply to the given Spond. */
  parentId?: string;
  parentHandle?: string;
  onSubmitted?: () => void;
}

export function SpondComposer({ lockedTicker, parentId, parentHandle, onSubmitted }: Props) {
  const { t } = useTranslation();
  const { user, isAuthenticated } = useAuth();
  const createSpond = useCreateSpond();
  const { requireVerification } = useEmailVerification();

  const [body, setBody] = useState("");
  const [ticker, setTicker] = useState(lockedTicker ?? "");
  const [error, setError] = useState<string | null>(null);

  // Signed-out users still see a small CTA — they can't compose at all.
  // Unverified signed-in users see the full composer; the verification
  // modal kicks in only when they hit Submit (and replays the post on
  // verification, via EmailVerificationProvider).
  if (!isAuthenticated) {
    return (
      <div style={composerCardStyle}>
        <p style={{ margin: 0, color: "#666" }}>
          {t("social.feed.login_to_post")}
        </p>
      </div>
    );
  }

  const remaining = SPOND_MAX_LENGTH - body.length;
  const isOver = remaining < 0;
  const isEmpty = body.trim().length === 0;
  const counterColor = remaining < 20 ? "#a00" : remaining < 80 ? "#a86600" : "#666";

  const placeholder = parentHandle
    ? t("social.compose.placeholder_reply", { handle: parentHandle })
    : lockedTicker
      ? t("social.compose.placeholder_company", { ticker: lockedTicker })
      : t("social.compose.placeholder");

  async function submitNow(payload: { body: string; ticker?: string; parent?: string }) {
    setError(null);
    try {
      await createSpond.mutateAsync(payload);
      setBody("");
      if (!lockedTicker) setTicker("");
      onSubmitted?.();
    } catch (e) {
      const wrap = e as Error & { status?: number; detail?: { body?: string[]; code?: string } };
      if (wrap.status === 429) {
        setError(t("social.errors.throttled"));
      } else if (wrap.status === 403) {
        setError(t("social.errors.email_verification_required"));
      } else if (wrap.detail?.body?.[0]?.includes?.("just posted")) {
        setError(t("social.errors.duplicate_body"));
      } else {
        setError(wrap.message || t("social.errors.body_too_long"));
      }
    }
  }

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (isEmpty || isOver) return;
    const payload = {
      body: body.trim(),
      ticker: ticker.trim() || undefined,
      parent: parentId,
    };
    // Unverified users get the verification modal; once they verify
    // (auth poll picks it up), the post submits automatically with the
    // body they had typed.
    requireVerification(() => submitNow(payload));
  }

  return (
    <form onSubmit={handleSubmit} style={composerCardStyle}>
      <div style={{ display: "flex", gap: "10px", alignItems: "flex-start" }}>
        <UserAvatar handle={user?.handle ?? null} displayName={user?.display_name} size="md" />
        <div style={{ flex: 1, minWidth: 0 }}>
          {parentHandle && (
            <div style={{ marginBottom: "6px", fontSize: "13px", color: "#666" }}>
              {t("social.compose.replying_to", { handle: parentHandle })}
            </div>
          )}
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            placeholder={placeholder}
            rows={3}
            maxLength={SPOND_MAX_LENGTH + 50}
            style={{
              width: "100%", minHeight: "72px", resize: "vertical",
              padding: "8px 10px", border: "1px solid #ccc", borderRadius: "6px",
              fontSize: "15px", fontFamily: "inherit",
            }}
          />
          <div
            style={{
              display: "flex", justifyContent: "space-between",
              alignItems: "center", marginTop: "6px", gap: "10px",
              flexWrap: "wrap",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              {lockedTicker ? (
                <span style={tickerChipStyle}>${lockedTicker}</span>
              ) : (
                <input
                  type="text"
                  value={ticker}
                  placeholder={t("social.compose.add_ticker")}
                  onChange={(e) => setTicker(e.target.value.toUpperCase())}
                  maxLength={10}
                  style={{
                    width: "120px", padding: "4px 8px",
                    border: "1px solid #ccc", borderRadius: "6px",
                    fontSize: "13px",
                  }}
                />
              )}
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <span style={{ fontSize: "13px", color: counterColor }}>
                {t("social.compose.char_left", { count: String(remaining) })}
              </span>
              <button
                type="submit"
                disabled={isEmpty || isOver || createSpond.isPending}
                style={{
                  padding: "6px 14px", border: "none", borderRadius: "6px",
                  background: isEmpty || isOver ? "#9aa" : "#1b347e",
                  color: "#fff", fontWeight: 600,
                  cursor: isEmpty || isOver || createSpond.isPending ? "not-allowed" : "pointer",
                }}
              >
                {t("social.compose.button")}
              </button>
            </div>
          </div>
          {error && (
            <div style={{ marginTop: "8px", padding: "6px 10px", background: "#fee", color: "#a00", borderRadius: "6px", fontSize: "13px" }}>
              {error}
            </div>
          )}
        </div>
      </div>
    </form>
  );
}

const composerCardStyle: React.CSSProperties = {
  padding: "12px",
  border: "1px solid #e1e4e8",
  borderRadius: "10px",
  background: "#ffffff",
  marginBottom: "16px",
};

const tickerChipStyle: React.CSSProperties = {
  display: "inline-block",
  padding: "3px 10px",
  borderRadius: "999px",
  background: "#eef1ff",
  color: "#1b347e",
  fontWeight: 600,
  fontSize: "13px",
};
