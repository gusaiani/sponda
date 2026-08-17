"use client";

import { useQuery } from "@tanstack/react-query";

import Link from "next/link";
import { useParams } from "next/navigation";
import { fetchSharedList, type SharedListData } from "../../../../hooks/useSavedLists";
import { useTranslation } from "../../../../i18n";

export default function SharedListPage() {
  const { t, locale, pluralize } = useTranslation();
  const { token: shareToken } = useParams<{ token: string }>();
  // react-query rather than fetch-in-an-effect. Besides dropping three pieces
  // of hand-synced state, it fixes the reason `t` had to be kept out of the
  // dependency array: error copy is now chosen at render time from the current
  // locale, so switching language re-labels the error instead of re-fetching.
  const {
    data: listData = null,
    isLoading,
    isError,
  } = useQuery<SharedListData>({
    queryKey: ["shared-list", shareToken],
    queryFn: () => fetchSharedList(shareToken),
    enabled: Boolean(shareToken),
    retry: false,
  });

  const error = !shareToken
    ? t("reset.invalid_link")
    : isError
      ? t("shared.not_found")
      : null;

  if (isLoading && shareToken) {
    return (
      <div className="auth-container">
        <div className="auth-card">
          <p className="auth-success-text">{t("common.loading")}</p>
        </div>
      </div>
    );
  }

  if (error || !listData) {
    return (
      <div className="auth-container">
        <div className="auth-card">
          <Link href={`/${locale}`} className="auth-logo-link">
            <span className="auth-logo">SPONDA</span>
          </Link>
          <h1 className="auth-title">{t("shared.not_found")}</h1>
          <p className="auth-success-text">
            {t("shared.expired_text")}
          </p>
          <p className="auth-link">
            <Link href={`/${locale}`}>{t("auth.go_to_homepage")}</Link>
          </p>
        </div>
      </div>
    );
  }

  const firstTicker = listData.tickers[0];
  const remainingTickers = listData.tickers.slice(1);
  const compareUrl = `/${locale}/${firstTicker}/comparar?extras=${remainingTickers.join(",")}&years=${listData.years}`;

  return (
    <div className="auth-container" style={{ maxWidth: "32rem" }}>
      <div className="auth-card">
        <Link href={`/${locale}`} className="auth-logo-link">
          <span className="auth-logo">SPONDA</span>
        </Link>
        <h1 className="auth-title">{t("shared.title")}</h1>

        <div style={{ marginBottom: "1.5rem" }}>
          <p className="auth-success-text" style={{ marginBottom: "0.5rem" }}>
            {t("shared.shared_list", { name: listData.shared_by })}
          </p>
          <p className="auth-success-text" style={{ fontSize: "1rem", color: "var(--color-ink)" }}>
            &ldquo;{listData.name}&rdquo;
          </p>
          <p className="auth-success-text">
            {listData.tickers.length} {t("common.companies")} · {listData.years} {pluralize(listData.years, "common.year_singular", "common.year_plural")} {t("common.of_analysis")}
          </p>
          <p className="auth-success-text" style={{ fontSize: "0.7rem" }}>
            Empresas: {listData.tickers.join(", ")}
          </p>
        </div>

        <Link
          href={compareUrl}
          className="auth-button"
          style={{ display: "block", textAlign: "center", textDecoration: "none" }}
        >
          {t("shared.view_list")}
        </Link>

        <p className="auth-link">
          <Link href={`/${locale}`}>{t("auth.go_to_homepage")}</Link>
        </p>
      </div>
    </div>
  );
}
