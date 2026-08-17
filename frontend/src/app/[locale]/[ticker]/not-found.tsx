"use client";

import Link from "next/link";
import { useTranslation } from "../../../i18n";

export default function TickerNotFound() {
  const { t, locale } = useTranslation();

  return (
    <div className="pe10-card" style={{ textAlign: "center", padding: "48px 16px" }}>
      <h2>{t("ticker.not_found_title")}</h2>
      <p style={{ marginTop: "8px", color: "var(--text-secondary)" }}>
        {t("ticker.not_found_text")}
      </p>
      {/* Same sentence as the account page's link, so it shares the key
          rather than carrying a second copy in all seven dictionaries. */}
      <Link href={`/${locale}`} style={{ marginTop: "16px", display: "inline-block" }}>
        {t("auth.back_to_homepage")}
      </Link>
    </div>
  );
}
