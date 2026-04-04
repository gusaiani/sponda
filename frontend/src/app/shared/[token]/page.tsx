"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { fetchSharedList, type SharedListData } from "../../../hooks/useSavedLists";
import { useTranslation } from "../../../i18n";

export default function SharedListPage() {
  const { t, pluralize } = useTranslation();
  const { token: shareToken } = useParams<{ token: string }>();
  const [listData, setListData] = useState<SharedListData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!shareToken) {
      setError(t("reset.invalid_link"));
      setIsLoading(false);
      return;
    }

    fetchSharedList(shareToken)
      .then((data) => setListData(data))
      .catch(() => setError(t("shared.not_found")))
      .finally(() => setIsLoading(false));
  }, [shareToken]);

  if (isLoading) {
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
          <Link href="/" className="auth-logo-link">
            <span className="auth-logo">SPONDA</span>
          </Link>
          <h1 className="auth-title">{t("shared.not_found")}</h1>
          <p className="auth-success-text">
            {t("shared.expired_text")}
          </p>
          <p className="auth-link">
            <Link href="/">{t("auth.go_to_homepage")}</Link>
          </p>
        </div>
      </div>
    );
  }

  const firstTicker = listData.tickers[0];
  const remainingTickers = listData.tickers.slice(1);
  const compareUrl = `/${firstTicker}/comparar?extras=${remainingTickers.join(",")}&years=${listData.years}`;

  return (
    <div className="auth-container" style={{ maxWidth: "32rem" }}>
      <div className="auth-card">
        <Link href="/" className="auth-logo-link">
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
          <Link href="/">{t("auth.go_to_homepage")}</Link>
        </p>
      </div>
    </div>
  );
}
