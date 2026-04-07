"use client";

import Link from "next/link";
import { useTranslation } from "../../../i18n";

export default function TickerNotFound() {
  const { t, locale } = useTranslation();

  return (
    <div className="pe10-card" style={{ textAlign: "center", padding: "48px 16px" }}>
      <h2>{locale === "pt" ? "Ticker não encontrado" : "Ticker not found"}</h2>
      <p style={{ marginTop: "8px", color: "var(--text-secondary)" }}>
        {locale === "pt"
          ? "O código informado não corresponde a nenhuma ação listada."
          : "The ticker you entered does not match any listed stock."}
      </p>
      <Link href={`/${locale}`} style={{ marginTop: "16px", display: "inline-block" }}>
        {locale === "pt" ? "Voltar para a página inicial" : "Back to home page"}
      </Link>
    </div>
  );
}
