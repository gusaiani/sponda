"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { SearchBar } from "../components/SearchBar";
import { AuthHeader } from "../components/AuthHeader";
import { FeedbackButton } from "../components/FeedbackButton";
import { usePageTracking } from "../hooks/usePageTracking";
import { POEMA_RETURN, IBOVESPA_RETURN, POEMA_PERIOD } from "../utils/branding";
import { useTranslation } from "../i18n";

const AUTH_PAGES = ["/login", "/signup", "/forgot-password", "/reset-password", "/verify-email"];

export function LayoutShell({ children }: { children: React.ReactNode }) {
  const { t } = useTranslation();
  usePageTracking();
  const router = useRouter();
  const pathname = usePathname();
  const queryClient = useQueryClient();
  const isOnAuthPage = AUTH_PAGES.some((path) => pathname.startsWith(path));

  function handleSearch(newTicker: string) {
    queryClient.invalidateQueries({ queryKey: ["pe10", newTicker] });
    queryClient.invalidateQueries({ queryKey: ["multiples-history", newTicker] });
    router.push(`/${newTicker}`);
  }

  return (
    <div className="app-container">
      {!isOnAuthPage && (
        <header className="app-header">
          <div className="app-header-top">
            <Link href="/" className="app-header-brand">
              <span className="app-header-logo">SPONDA</span>
              <span className="app-header-tagline">{t("header.tagline")}</span>
            </Link>
            <AuthHeader />
          </div>
          <div className="app-header-search-row">
            <SearchBar onSearch={handleSearch} isLoading={false} />
          </div>
        </header>
      )}
      {isOnAuthPage && <AuthHeader />}
      <FeedbackButton />
      <main className="app-main">
        {children}
      </main>
      <footer className="app-footer">
        <a href="https://poe.ma" target="_blank" rel="noopener noreferrer" className="app-footer-logo-link">
          <Image src="/poema-logo.jpg" alt="Poema" className="app-footer-logo" width={42} height={42} />
        </a>
        <p className="app-footer-text">
          {t("footer.tool_by")}{" "}
          <a href="https://poe.ma" target="_blank" rel="noopener noreferrer" className="app-footer-link">
            Poema Parceria de Investimentos
          </a>
        </p>
        <a href="https://poe.ma" target="_blank" rel="noopener noreferrer" className="app-footer-link app-footer-performance">
          {t("footer.cumulative_return", { poemaReturn: POEMA_RETURN, ibovespaReturn: IBOVESPA_RETURN, period: POEMA_PERIOD })}
          <br />
          {t("footer.past_results")}
        </a>
        <a href="https://poe.ma" target="_blank" rel="noopener noreferrer" className="app-footer-link app-footer-cta">
          {t("footer.looking_for_partners")}
        </a>
      </footer>
    </div>
  );
}
