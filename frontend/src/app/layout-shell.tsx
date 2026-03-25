"use client";

import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { SearchBar } from "../components/SearchBar";
import { AuthHeader } from "../components/AuthHeader";
import { FeedbackButton } from "../components/FeedbackButton";
import { usePageTracking } from "../hooks/usePageTracking";
import { POEMA_PERFORMANCE_LINE, POEMA_DISCLAIMER, POEMA_CTA } from "../utils/branding";

const AUTH_PAGES = ["/login", "/signup", "/forgot-password", "/reset-password", "/verify-email"];

export function LayoutShell({ children }: { children: React.ReactNode }) {
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
              <span className="app-header-tagline">Para investidores em valor</span>
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
          <img src="/poema-logo.jpg" alt="Poema" className="app-footer-logo" />
        </a>
        <p className="app-footer-text">
          Uma ferramenta da{" "}
          <a href="https://poe.ma" target="_blank" rel="noopener noreferrer" className="app-footer-link">
            Poema Parceria de Investimentos
          </a>
        </p>
        <a href="https://poe.ma" target="_blank" rel="noopener noreferrer" className="app-footer-link app-footer-performance">
          {POEMA_PERFORMANCE_LINE}
          <br />
          {POEMA_DISCLAIMER}
        </a>
        <a href="https://poe.ma" target="_blank" rel="noopener noreferrer" className="app-footer-link app-footer-cta">
          {POEMA_CTA}
        </a>
      </footer>
    </div>
  );
}
