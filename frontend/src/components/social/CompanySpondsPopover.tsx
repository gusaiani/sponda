"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useTranslation } from "../../i18n";
import { SpondComposer } from "./SpondComposer";
import { SpondFeed } from "./SpondFeed";

interface Props {
  ticker: string;
  open: boolean;
  onClose: () => void;
}

/**
 * Quick "what are people saying?" overlay anchored to a company card.
 * Shows the per-ticker Spond feed and a locked-ticker composer in a
 * centered modal, so the user can read and post without leaving the
 * homepage. Same content as the dedicated /[ticker]/sponds tab,
 * different presentation.
 */
export function CompanySpondsPopover({ ticker, open, onClose }: Props) {
  const { t, locale } = useTranslation();

  useEffect(() => {
    if (!open) return;
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={t("social.card.popover_title", { ticker })}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
      style={{
        position: "fixed", inset: 0, zIndex: 1000,
        background: "rgba(0,0,0,0.4)",
        display: "flex", alignItems: "center", justifyContent: "center",
        padding: "16px",
      }}
    >
      <div
        style={{
          background: "#fff",
          borderRadius: "12px",
          width: "100%",
          maxWidth: "560px",
          maxHeight: "80vh",
          display: "flex",
          flexDirection: "column",
          boxShadow: "0 16px 48px rgba(0, 0, 0, 0.2)",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "12px 16px",
            borderBottom: "1px solid #e1e4e8",
            background: "#fafbfc",
            borderRadius: "12px 12px 0 0",
          }}
        >
          <Link
            href={`/${locale}/${ticker}`}
            style={{ color: "#1b347e", fontWeight: 700, fontSize: "16px", textDecoration: "none" }}
          >
            {t("social.card.popover_title", { ticker })}
          </Link>
          <button
            type="button"
            onClick={onClose}
            aria-label={t("common.close")}
            style={{
              background: "none", border: "none", cursor: "pointer",
              padding: "4px 8px", color: "#666", fontSize: "20px", lineHeight: 1,
            }}
          >
            ×
          </button>
        </div>
        <div style={{ overflowY: "auto", padding: "12px", flex: 1 }}>
          <SpondComposer lockedTicker={ticker} />
          <SpondFeed kind="company" ticker={ticker} />
        </div>
      </div>
    </div>
  );
}
