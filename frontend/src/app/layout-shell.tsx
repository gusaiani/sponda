"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { AssistantBar } from "../components/assistant/AssistantBar";
import { SearchBar } from "../components/SearchBar";
import { AuthHeader } from "../components/AuthHeader";
import { FeedbackProvider } from "../components/FeedbackButton";
import { EmailVerificationProvider } from "../components/EmailVerificationGate";
import { LeftNav } from "../components/LeftNav";
import { LeftNavProvider, useLeftNav } from "../components/LeftNavContext";
import { SocialSidebar } from "../components/social/SocialSidebar";
import { usePageTracking } from "../hooks/usePageTracking";
import { useAuth } from "../hooks/useAuth";
import { POEMA_RETURN, IBOVESPA_RETURN, POEMA_PERIOD } from "../utils/branding";
import { resolveTab } from "../utils/tabs";
import { useTranslation } from "../i18n";
import "../styles/social-sidebar.css";
import "../styles/left-nav.css";

const AUTH_SUFFIXES = [
  "/login",
  "/signup",
  "/forgot-password",
  "/reset-password",
];

const NON_COMPANY_SEGMENTS = new Set([
  "account",
  "admin",
  "admin-dashboard",
  "alertas",
  "forgot-password",
  "listas",
  "login",
  "notificacoes",
  "reset-password",
  "screener",
  "shared",
  "signup",
  "spond",
  "user",
  "verify-email",
  "visitas",
]);

/** Return the ticker when `bare` is a company page, otherwise null. */
function companyTickerFromPath(bare: string): string | null {
  const segments = bare.split("/").filter(Boolean);
  const firstSegment = segments[0];
  if (!firstSegment || NON_COMPANY_SEGMENTS.has(firstSegment)) return null;
  return firstSegment.toUpperCase();
}

/** Strip the locale prefix from a pathname for matching purposes. */
function stripLocale(pathname: string): string {
  const match = pathname.match(/^\/(pt|en)(\/.*)?$/);
  return match ? match[2] || "/" : pathname;
}

function HamburgerToggle() {
  const { t } = useTranslation();
  const { open, toggle } = useLeftNav();
  return (
    <button
      type="button"
      className="app-hamburger"
      onClick={toggle}
      aria-label={open ? t("nav.toggle_close") : t("nav.toggle_open")}
      aria-expanded={open}
    >
      <svg
        width="22"
        height="22"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <line x1="3" y1="6" x2="21" y2="6" />
        <line x1="3" y1="12" x2="21" y2="12" />
        <line x1="3" y1="18" x2="21" y2="18" />
      </svg>
    </button>
  );
}

function LayoutShellInner({ children }: { children: React.ReactNode }) {
  const { t, locale } = useTranslation();
  usePageTracking();
  const router = useRouter();
  const pathname = usePathname();
  const queryClient = useQueryClient();
  const { isSuperuser } = useAuth();
  const bare = stripLocale(pathname);
  const isOnAuthPage = AUTH_SUFFIXES.some((suffix) => bare.startsWith(suffix));
  const companyTicker = companyTickerFromPath(bare);

  function handleSearch(newTicker: string) {
    queryClient.invalidateQueries({ queryKey: ["pe10", newTicker] });
    queryClient.invalidateQueries({
      queryKey: ["multiples-history", newTicker],
    });
    router.push(`/${locale}/${newTicker}`);
  }

  const brand = (
    <Link href={`/${locale}`} className="app-header-brand">
      <span className="app-header-logo">SPONDA</span>
      <span className="app-header-tagline">{t("header.tagline")}</span>
    </Link>
  );

  return (
    <div className="app-container">
      {isOnAuthPage ? (
        <header className="app-header app-header-auth">
          {brand}
          <AuthHeader />
        </header>
      ) : (
        <header className="app-header">
          <HamburgerToggle />
          {brand}
          <SearchBar onSearch={handleSearch} isLoading={false} />
          <Link href={`/${locale}/screener`} className="app-header-filter-link">
            {t("screener.link_label")}
          </Link>
          <AuthHeader />
        </header>
      )}
      {!isOnAuthPage && <LeftNav />}
      <div className="app-body">
        <main className="app-main">{children}</main>
      </div>
      {!isOnAuthPage && <SocialSidebar />}
      {!isOnAuthPage && companyTicker && isSuperuser && (
        <AssistantBar ticker={companyTicker} tab={resolveTab(pathname)} />
      )}
      <footer className="app-footer">
        <a
          href="https://poe.ma"
          target="_blank"
          rel="noopener noreferrer"
          className="app-footer-logo-link"
        >
          <Image
            src="/poema-logo.jpg"
            alt="Poema"
            className="app-footer-logo"
            width={42}
            height={42}
          />
        </a>
        <p className="app-footer-text">
          {t("footer.tool_by")}{" "}
          <a
            href="https://poe.ma"
            target="_blank"
            rel="noopener noreferrer"
            className="app-footer-link"
          >
            Poema Parceria de Investimentos
          </a>
        </p>
        <a
          href="https://poe.ma"
          target="_blank"
          rel="noopener noreferrer"
          className="app-footer-link app-footer-performance"
        >
          {t("footer.cumulative_return", {
            poemaReturn: POEMA_RETURN,
            ibovespaReturn: IBOVESPA_RETURN,
            period: POEMA_PERIOD,
          })}
          <br />
          {t("footer.past_results")}
        </a>
        <a
          href="https://poe.ma"
          target="_blank"
          rel="noopener noreferrer"
          className="app-footer-link app-footer-cta"
        >
          {t("footer.looking_for_partners")}
        </a>
      </footer>
    </div>
  );
}

export function LayoutShell({ children }: { children: React.ReactNode }) {
  return (
    <LeftNavProvider>
      <FeedbackProvider>
        <EmailVerificationProvider>
          <LayoutShellInner>{children}</LayoutShellInner>
        </EmailVerificationProvider>
      </FeedbackProvider>
    </LeftNavProvider>
  );
}
