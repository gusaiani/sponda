"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTranslation, LanguageToggle } from "../i18n";
import { useAuth } from "../hooks/useAuth";
import { useLearningMode } from "../learning";
import { useFeedback } from "./FeedbackButton";
import { useLeftNav } from "./LeftNavContext";
import "../styles/left-nav.css";

/**
 * YouTube-style fixed left rail. When `open` is true the nav is 240px and
 * shows labels; when false it is hidden (0px). Hamburger in the top header
 * toggles via the LeftNav context. All secondary header items have moved
 * here: Learning Mode toggle, Alerts, Visits, Blog, Share, Feedback.
 */
export function LeftNav() {
  const { t, locale } = useTranslation();
  const { open, setOpen } = useLeftNav();
  const { isAuthenticated, isSuperuser } = useAuth();
  const learningMode = useLearningMode();
  const pathname = usePathname();
  const feedback = useFeedback();

  if (!open) return null;

  function close() {
    if (typeof window !== "undefined" && window.innerWidth < 900) {
      setOpen(false);
    }
  }

  return (
    <>
      <div className="left-nav-backdrop" onClick={() => setOpen(false)} />

      <nav className="left-nav" aria-label={t("nav.account_menu_label")}>
        <ul className="left-nav-list">
          <li>
            <Link
              href={`/${locale}`}
              className={navItemClass(pathname === `/${locale}` || pathname === `/${locale}/`)}
              onClick={close}
            >
              <span className="left-nav-icon"><HomeIcon /></span>
              <span className="left-nav-label">{t("nav.home")}</span>
            </Link>
          </li>

          {isAuthenticated && (
            <li>
              <Link
                href={`/${locale}/alertas`}
                className={navItemClass(pathname.startsWith(`/${locale}/alertas`))}
                onClick={close}
              >
                <span className="left-nav-icon"><BellIcon /></span>
                <span className="left-nav-label">{t("alerts.page_title")}</span>
              </Link>
            </li>
          )}

          {isAuthenticated && (
            <li>
              <Link
                href={`/${locale}/visitas`}
                className={navItemClass(pathname.startsWith(`/${locale}/visitas`))}
                onClick={close}
              >
                <span className="left-nav-icon"><EyeIcon /></span>
                <span className="left-nav-label">{t("visits.page_title")}</span>
              </Link>
            </li>
          )}

          <li>
            <a
              href="https://blog.sponda.capital"
              target="_blank"
              rel="noopener noreferrer"
              className={navItemClass(false)}
              onClick={close}
            >
              <span className="left-nav-icon"><FileIcon /></span>
              <span className="left-nav-label">{t("nav.blog")}</span>
            </a>
          </li>

          {isSuperuser && (
            <li>
              <Link
                href={`/${locale}/admin-dashboard`}
                className={navItemClass(pathname.startsWith(`/${locale}/admin`))}
                onClick={close}
              >
                <span className="left-nav-icon"><ShieldIcon /></span>
                <span className="left-nav-label">Admin</span>
              </Link>
            </li>
          )}

          <li><div className="left-nav-divider" /></li>

          {learningMode.available && (
            <li>
              <button
                type="button"
                className={navItemClass(false)}
                aria-pressed={learningMode.enabled}
                onClick={() => learningMode.setEnabled(!learningMode.enabled)}
              >
                <span className="left-nav-icon"><LearningModeDots /></span>
                <span className="left-nav-label">{t("learning.toggle.label")}</span>
                <span className={`left-nav-state-pill left-nav-state-pill--${learningMode.enabled ? "on" : "off"}`}>
                  {learningMode.enabled ? "ON" : "OFF"}
                </span>
              </button>
            </li>
          )}

          <li>
            <ShareNavItem onSelect={close} />
          </li>

          <li>
            <button
              type="button"
              className={navItemClass(false)}
              onClick={() => {
                close();
                feedback.open();
              }}
            >
              <span className="left-nav-icon"><MailIcon /></span>
              <span className="left-nav-label">{t("feedback.trigger")}</span>
            </button>
          </li>
        </ul>

        <div className="left-nav-section">
          <div className="left-nav-section-row">
            <LanguageToggle />
          </div>
        </div>
      </nav>
    </>
  );
}

function navItemClass(active: boolean): string {
  return `left-nav-item${active ? " left-nav-item--active" : ""}`;
}

/**
 * Share affordance, matching the visual rhythm of the other nav items.
 * Wraps the existing copy-link / share-target list inline so users don't
 * have to leave the rail. Clicking the row toggles the inline section
 * just like an accordion.
 */
function ShareNavItem({ onSelect }: { onSelect: () => void }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function clickOutside(event: MouseEvent) {
      if (ref.current && !ref.current.contains(event.target as Node)) setOpen(false);
    }
    if (open) document.addEventListener("mousedown", clickOutside);
    return () => document.removeEventListener("mousedown", clickOutside);
  }, [open]);

  const url = typeof window === "undefined"
    ? "https://sponda.capital"
    : `https://sponda.capital${window.location.pathname}`;
  const text = t("share.text_without_ticker");
  const encodedUrl = encodeURIComponent(url);
  const encodedText = encodeURIComponent(text);

  function copyLink() {
    if (typeof navigator !== "undefined") navigator.clipboard.writeText(url);
    setCopied(true);
    setTimeout(() => {
      setCopied(false);
      setOpen(false);
      onSelect();
    }, 1200);
  }

  return (
    <div ref={ref}>
      <button
        type="button"
        className={navItemClass(false)}
        onClick={() => setOpen((prev) => !prev)}
        aria-expanded={open}
      >
        <span className="left-nav-icon"><ShareIcon /></span>
        <span className="left-nav-label">{t("share.label")}</span>
      </button>
      {open && (
        <div style={{ padding: "4px 12px 8px 64px", display: "flex", flexDirection: "column", gap: "4px" }}>
          <a
            href={`https://x.com/intent/tweet?text=${encodedText}&url=${encodedUrl}`}
            target="_blank"
            rel="noopener noreferrer"
            style={shareSubItemStyle}
            onClick={() => { setOpen(false); onSelect(); }}
          >
            X / Twitter
          </a>
          <a
            href={`https://wa.me/?text=${encodedText}%20${encodedUrl}`}
            target="_blank"
            rel="noopener noreferrer"
            style={shareSubItemStyle}
            onClick={() => { setOpen(false); onSelect(); }}
          >
            WhatsApp
          </a>
          <a
            href={`https://t.me/share/url?url=${encodedUrl}&text=${encodedText}`}
            target="_blank"
            rel="noopener noreferrer"
            style={shareSubItemStyle}
            onClick={() => { setOpen(false); onSelect(); }}
          >
            Telegram
          </a>
          <a
            href={`https://www.linkedin.com/sharing/share-offsite/?url=${encodedUrl}`}
            target="_blank"
            rel="noopener noreferrer"
            style={shareSubItemStyle}
            onClick={() => { setOpen(false); onSelect(); }}
          >
            LinkedIn
          </a>
          <button type="button" onClick={copyLink} style={{ ...shareSubItemStyle, background: "none", border: "none", cursor: "pointer", textAlign: "left" }}>
            {copied ? t("share.copied") : t("share.copy_link")}
          </button>
        </div>
      )}
    </div>
  );
}

const shareSubItemStyle: React.CSSProperties = {
  fontSize: "13px",
  color: "#1b347e",
  textDecoration: "none",
  padding: "4px 8px",
  borderRadius: "6px",
};


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

function ShareIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="20" height="20" aria-hidden>
      <circle cx="18" cy="5" r="3" />
      <circle cx="6" cy="12" r="3" />
      <circle cx="18" cy="19" r="3" />
      <line x1="8.59" y1="13.51" x2="15.42" y2="17.49" />
      <line x1="15.41" y1="6.51" x2="8.59" y2="10.49" />
    </svg>
  );
}

function MailIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="20" height="20" aria-hidden>
      <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
      <polyline points="22,6 12,13 2,6" />
    </svg>
  );
}

/** Three small dots in beginner / advanced colors — matches the chip
 * affordance from the previous LearningModeToggle. */
function LearningModeDots() {
  return (
    <span style={{ display: "inline-flex", gap: "2px" }}>
      <span style={{ width: "6px", height: "6px", borderRadius: "50%", background: "#dc2626" }} />
      <span style={{ width: "6px", height: "6px", borderRadius: "50%", background: "#d97706" }} />
      <span style={{ width: "6px", height: "6px", borderRadius: "50%", background: "#15803d" }} />
    </span>
  );
}
