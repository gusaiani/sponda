import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "../hooks/useAuth";
import { useTranslation, LanguageToggle } from "../i18n";
import { ShareDropdown } from "./ShareDropdown";
import { NotificationBell } from "./NotificationBell";
import "../styles/auth-header.css";

const AUTH_PAGES = ["/login", "/signup", "/forgot-password", "/reset-password"];

export function AuthHeader() {
  const { user, isAuthenticated, isSuperuser, isLoading } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const { t, locale } = useTranslation();
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Strip locale prefix (e.g. `/pt/login` → `/login`) before matching,
  // so auth-page detection works under the i18n routing segment.
  const pathWithoutLocale = pathname.replace(/^\/[a-z]{2}(?=\/|$)/, "") || "/";
  const isOnAuthPage = AUTH_PAGES.some((path) => pathWithoutLocale.startsWith(path));

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  if (isLoading) {
    return (
      <div className="auth-header auth-header--loading">
        <span className="auth-header-link auth-header-signup">&nbsp;</span>
      </div>
    );
  }

  function closeMenu() {
    setIsMenuOpen(false);
  }

  return (
    <div className="auth-header">
      <NotificationBell />

      {/* Inline items — visible on desktop, hidden on mobile */}
      <div className="auth-header-inline">
        {isAuthenticated && !user?.email_verified && (
          <div className="auth-header-tooltip-group">
            <Link href={`/${locale}/verify-email`} className="auth-header-link auth-header-warning-pill">
              {t("auth.email_not_verified_link")}
            </Link>
            <div className="auth-header-tooltip" role="tooltip">
              <p className="auth-header-tooltip-title">{t("auth.email_not_verified_tooltip_title")}</p>
              <ul className="auth-header-tooltip-list">
                <li>{t("auth.email_not_verified_tooltip_queries")}</li>
                <li>{t("auth.email_not_verified_tooltip_favorites")}</li>
                <li>{t("auth.email_not_verified_tooltip_features")}</li>
              </ul>
            </div>
          </div>
        )}
        <ShareDropdown />
        <a href="https://blog.sponda.capital" className="auth-header-link" target="_blank" rel="noopener noreferrer">
          Blog
        </a>
        {isAuthenticated && (
          <>
            <Link href={`/${locale}/visitas`} className="auth-header-link">
              {t("visits.page_title")}
            </Link>
            <Link href={`/${locale}/alertas`} className="auth-header-link">
              {t("alerts.page_title")}
            </Link>
            {isSuperuser && (
              <Link href={`/${locale}/admin-dashboard`} className="auth-header-link auth-header-admin">
                Admin
              </Link>
            )}
          </>
        )}
        <LanguageToggle />
        {isAuthenticated && (
          <Link href={`/${locale}/account`} className="auth-header-link">
            {t("auth.my_account")}
          </Link>
        )}
        {!isAuthenticated && (isOnAuthPage ? (
          <button
            className="auth-header-link auth-header-close"
            onClick={() => router.push(`/${locale}`)}
            aria-label={t("common.close")}
          >
            ✕
          </button>
        ) : (
          <Link href={`/${locale}/login`} className="auth-header-link auth-header-signup">
            {t("auth.login")}
          </Link>
        ))}
      </div>

      {/* Hamburger — visible on mobile, hidden on desktop */}
      <div className="auth-header-hamburger-wrapper" ref={menuRef}>
        <button
          type="button"
          className="auth-header-hamburger"
          aria-label={t("header.menu")}
          aria-expanded={isMenuOpen}
          onClick={() => setIsMenuOpen((open) => !open)}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="3" y1="6" x2="21" y2="6" />
            <line x1="3" y1="12" x2="21" y2="12" />
            <line x1="3" y1="18" x2="21" y2="18" />
          </svg>
        </button>
        {isMenuOpen && (
          <div className="auth-header-menu" role="menu">
            {isAuthenticated && !user?.email_verified && (
              <Link
                href={`/${locale}/verify-email`}
                className="auth-header-menu-link auth-header-warning"
                onClick={closeMenu}
              >
                {t("auth.email_not_verified_link")}
              </Link>
            )}
            <div className="auth-header-menu-row auth-header-menu-row--controls">
              <ShareDropdown />
              <LanguageToggle />
            </div>
            <a
              href="https://blog.sponda.capital"
              className="auth-header-menu-link"
              target="_blank"
              rel="noopener noreferrer"
              onClick={closeMenu}
            >
              Blog
            </a>
            {isAuthenticated && (
              <>
                <Link
                  href={`/${locale}/visitas`}
                  className="auth-header-menu-link"
                  onClick={closeMenu}
                >
                  {t("visits.page_title")}
                </Link>
                <Link
                  href={`/${locale}/alertas`}
                  className="auth-header-menu-link"
                  onClick={closeMenu}
                >
                  {t("alerts.page_title")}
                </Link>
                {isSuperuser && (
                  <Link
                    href={`/${locale}/admin-dashboard`}
                    className="auth-header-menu-link auth-header-admin"
                    onClick={closeMenu}
                  >
                    Admin
                  </Link>
                )}
                <Link
                  href={`/${locale}/account`}
                  className="auth-header-menu-link"
                  onClick={closeMenu}
                >
                  {t("auth.my_account")}
                </Link>
              </>
            )}
            {!isAuthenticated && !isOnAuthPage && (
              <Link
                href={`/${locale}/login`}
                className="auth-header-menu-link auth-header-signup"
                onClick={closeMenu}
              >
                {t("auth.login")}
              </Link>
            )}
            {!isAuthenticated && isOnAuthPage && (
              <button
                className="auth-header-menu-link auth-header-close"
                onClick={() => { closeMenu(); router.push(`/${locale}`); }}
                aria-label={t("common.close")}
              >
                {t("common.close")}
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
