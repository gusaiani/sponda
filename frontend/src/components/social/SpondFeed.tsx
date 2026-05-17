"use client";

import { useTranslation } from "../../i18n";
import { useSocialFeed, type FeedKind } from "../../hooks/useSocialFeed";
import { SpondCard } from "./SpondCard";

interface Props {
  kind: FeedKind;
  ticker?: string;
}

export function SpondFeed({ kind, ticker }: Props) {
  const { t } = useTranslation();
  const query = useSocialFeed(kind, ticker);

  if (query.isLoading) {
    return <div style={{ padding: "16px", color: "#666" }}>{t("common.loading")}</div>;
  }

  const all = (query.data?.pages ?? []).flatMap((page) => page.results);

  if (all.length === 0) {
    const emptyKey =
      kind === "following" ? "social.feed.empty_following"
        : kind === "company" ? "social.feed.empty_company"
        : "social.feed.empty_global";
    const message = kind === "company" && ticker
      ? t("social.feed.empty_company", { ticker })
      : t(emptyKey);
    return <div style={{ padding: "16px", color: "#666" }}>{message}</div>;
  }

  return (
    <div>
      {all.map((spond) => (
        <SpondCard key={spond.id} spond={spond} />
      ))}
      {query.hasNextPage && (
        <div style={{ textAlign: "center", padding: "12px" }}>
          <button
            type="button"
            onClick={() => query.fetchNextPage()}
            disabled={query.isFetchingNextPage}
            style={{
              padding: "6px 14px", border: "1px solid #ccc",
              borderRadius: "6px", background: "#fff", cursor: "pointer",
            }}
          >
            {query.isFetchingNextPage ? t("common.loading") : "…"}
          </button>
        </div>
      )}
    </div>
  );
}
