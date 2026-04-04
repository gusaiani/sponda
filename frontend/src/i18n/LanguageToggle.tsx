"use client";

import { useTranslation } from "./useTranslation";
import type { Locale } from "./types";

export function LanguageToggle() {
  const { locale, setLocale } = useTranslation();

  function handleToggle() {
    const next: Locale = locale === "pt" ? "en" : "pt";
    setLocale(next);
  }

  return (
    <button
      className="language-toggle"
      onClick={handleToggle}
      aria-label={locale === "pt" ? "Switch to English" : "Mudar para Portugu\u00eas"}
      title={locale === "pt" ? "Switch to English" : "Mudar para Portugu\u00eas"}
    >
      <span className="language-toggle-label">{locale === "pt" ? "EN" : "PT"}</span>
    </button>
  );
}
