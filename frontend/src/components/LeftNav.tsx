"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTranslation, LanguageToggle } from "../i18n";
import { useAuth } from "../hooks/useAuth";
import { LearningModeToggle } from "./LearningModeToggle";
import { ShareDropdown } from "./ShareDropdown";
import { useLeftNav } from "./LeftNavContext";
import "../styles/left-nav.css";

/**
 * YouTube-style fixed left rail. When `open` is true the nav is 240px and
 * shows labels; when false it is hidden (0px). Hamburger in the top header
 * toggles via the LeftNav context. All secondary header items have moved
 * here: Learning Mode toggle, Alerts, Visits, Blog, Share, Language, Admin.
 */
export function LeftNav() {
  const { t, locale } = useTranslation();
  const { open, setOpen } = useLeftNav();
  const { isAuthenticated, isSuperuser } = useAuth();
  const pathname = usePathname();

  const items = [
    {
      href: `/${locale}`,
      label: t("nav.home"),
      icon: <HomeIcon />,
      active: pathname === `/${locale}` || pathname === `/${locale}/`,
    },
    isAuthenticated && {
      href: `/${locale}/alertas`,
      label: t("alerts.page_title"),
      icon: <BellIcon />,
      active: pathname.startsWith(`/${locale}/alertas`),
    },
    isAuthenticated && {
      href: `/${locale}/visitas`,
      label: t("visits.page_title"),
      icon: <EyeIcon />,
      active: pathname.startsWith(`/${locale}/visitas`),
    },
    isAuthenticated && {
      href: `/${locale}/listas`,
      label: t("nav.lists" in {} ? "nav.home" : "nav.home"), // unused branch; lists key absent
      icon: null,
      active: false,
      hidden: true,
    },
    {
      href: "https://blog.sponda.capital",
      label: t("nav.blog"),
      icon: <FileIcon />,
      external: true,
    },
    isSuperuser && {
      href: `/${locale}/admin-dashboard`,
      label: "Admin",
      icon: <ShieldIcon />,
      active: pathname.startsWith(`/${locale}/admin`),
    },
  ].filter(Boolean) as Array<{
    href: string;
    label: string;
    icon: React.ReactNode;
    active?: boolean;
    external?: boolean;
    hidden?: boolean;
  }>;

  if (!open) return null;

  function close() {
    // On narrow viewports, clicking a link should auto-close the overlay.
    if (typeof window !== "undefined" && window.innerWidth < 900) {
      setOpen(false);
    }
  }

  return (
    <>
      {/* Backdrop on mobile to dim the rest of the page. */}
      <div className="left-nav-backdrop" onClick={() => setOpen(false)} />

      <nav className="left-nav" aria-label={t("nav.account_menu_label")}>
        <ul className="left-nav-list">
          {items.filter((item) => !item.hidden).map((item) => (
            <li key={item.label}>
              {item.external ? (
                <a
                  href={item.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="left-nav-item"
                  onClick={close}
                >
                  <span className="left-nav-icon">{item.icon}</span>
                  <span className="left-nav-label">{item.label}</span>
                </a>
              ) : (
                <Link
                  href={item.href}
                  className={`left-nav-item${item.active ? " left-nav-item--active" : ""}`}
                  onClick={close}
                >
                  <span className="left-nav-icon">{item.icon}</span>
                  <span className="left-nav-label">{item.label}</span>
                </Link>
              )}
            </li>
          ))}
        </ul>

        <div className="left-nav-section">
          <div className="left-nav-section-row">
            <LearningModeToggle />
          </div>
          <div className="left-nav-section-row">
            <ShareDropdown />
          </div>
          <div className="left-nav-section-row">
            <LanguageToggle />
          </div>
        </div>
      </nav>
    </>
  );
}

/* ── Icons ────────────────────────────────────────────────────────────── */

function HomeIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="20" height="20" aria-hidden>
      <path d="M3 12l9-9 9 9" />
      <path d="M5 10v10h14V10" />
    </svg>
  );
}

function BellIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="20" height="20" aria-hidden>
      <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.73 21a2 2 0 0 1-3.46 0" />
    </svg>
  );
}

function EyeIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="20" height="20" aria-hidden>
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function FileIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="20" height="20" aria-hidden>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <path d="M14 2v6h6" />
    </svg>
  );
}

function ShieldIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="20" height="20" aria-hidden>
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  );
}
