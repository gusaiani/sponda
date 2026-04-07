"use client";

import { useState, FormEvent } from "react";
import Link from "next/link";
import { useAuth } from "../../../hooks/useAuth";
import { csrfHeaders } from "../../../utils/csrf";
import { useTranslation, type TranslationKey } from "../../../i18n";

function formatTimeSince(dateString: string, pluralize: (count: number, singular: TranslationKey, plural: TranslationKey) => string): string {
  const joined = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - joined.getTime();

  const minutes = Math.floor(diffMs / (1000 * 60));
  const hours = Math.floor(diffMs / (1000 * 60 * 60));
  const days = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  const months = Math.floor(days / 30);
  const years = Math.floor(days / 365);

  if (years > 0) return `${years} ${pluralize(years, "common.year_singular", "common.year_plural")}`;
  if (months > 0) return `${months} ${pluralize(months, "common.month_singular", "common.month_plural")}`;
  if (days > 0) return `${days} ${pluralize(days, "common.day_singular", "common.day_plural")}`;
  if (hours > 0) return `${hours} ${pluralize(hours, "common.hour_singular", "common.hour_plural")}`;
  return `${minutes} ${pluralize(minutes, "common.minute_singular", "common.minute_plural")}`;
}

function formatDate(dateString: string, locale: string): string {
  return new Date(dateString).toLocaleDateString(locale === "pt" ? "pt-BR" : "en-US", {
    day: "2-digit",
    month: "long",
    year: "numeric",
  });
}

type AccountView = "main" | "change-password";

export default function AccountPage() {
  const { user, isLoading, isAuthenticated, logout } = useAuth();
  const [view, setView] = useState<AccountView>("main");
  const { t, locale, pluralize } = useTranslation();

  if (isLoading) {
    return (
      <div className="auth-container">
        <div className="auth-card">
          <p className="auth-success-text">{t("common.loading")}</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated || !user) {
    return (
      <div className="auth-container">
        <div className="auth-card">
          <Link href={`/${locale}`} className="auth-logo-link">
            <span className="auth-logo">SPONDA</span>
          </Link>
          <h1 className="auth-title">{t("auth.restricted_access")}</h1>
          <p className="auth-success-text">
            {t("auth.must_be_logged_in")}
          </p>
          <p className="auth-link">
            <Link href={`/${locale}/login`}>{t("auth.do_login")}</Link>
          </p>
        </div>
      </div>
    );
  }

  async function handleLogout() {
    await logout();
    window.location.href = `/${locale}`;
  }

  if (view === "change-password") {
    return <ChangePasswordView onBack={() => setView("main")} />;
  }

  return (
    <div className="auth-container">
      <div className="auth-card">
        <Link href={`/${locale}`} className="auth-logo-link">
          <span className="auth-logo">SPONDA</span>
        </Link>
        <h1 className="auth-title">{t("auth.my_account")}</h1>

        <p className="account-membership">
          {t("auth.member_since")}{" "}
          <strong>{formatDate(user.date_joined, locale)}</strong>
          {" "}— {formatTimeSince(user.date_joined, pluralize)}.
        </p>

        <div className="account-actions">
          <button
            type="button"
            className="account-action-link"
            onClick={() => setView("change-password")}
          >
            {t("auth.change_password")}
          </button>
          <button
            type="button"
            className="account-action-link"
            onClick={handleLogout}
          >
            {t("auth.logout")}
          </button>
        </div>

        <p className="auth-link">
          <Link href={`/${locale}`}>{t("auth.back_to_homepage")}</Link>
        </p>
      </div>
    </div>
  );
}

function ChangePasswordView({ onBack }: { onBack: () => void }) {
  const { t, locale } = useTranslation();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSuccess(null);

    if (newPassword !== confirmPassword) {
      setError(t("auth.passwords_dont_match"));
      return;
    }

    setLoading(true);

    try {
      const response = await fetch("/api/auth/change-password/", {
        method: "POST",
        headers: csrfHeaders(),
        credentials: "include",
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      });

      if (!response.ok) {
        const data = await response.json();
        setError(data.error || t("auth.change_password_error"));
        return;
      }

      setSuccess(t("auth.password_changed"));
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch {
      setError(t("auth.connection_error"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-container">
      <div className="auth-card">
        <Link href={`/${locale}`} className="auth-logo-link">
          <span className="auth-logo">SPONDA</span>
        </Link>
        <h1 className="auth-title">{t("auth.change_password_title")}</h1>

        <form className="auth-form" onSubmit={handleSubmit}>
          <div>
            <label className="auth-label" htmlFor="current-password">
              {t("auth.current_password")}
            </label>
            <input
              id="current-password"
              type="password"
              className="auth-input"
              value={currentPassword}
              onChange={(event) => setCurrentPassword(event.target.value)}
              required
              autoFocus
            />
          </div>
          <div>
            <label className="auth-label" htmlFor="new-password">
              {t("auth.new_password")}
            </label>
            <input
              id="new-password"
              type="password"
              className="auth-input"
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
              minLength={8}
              required
            />
            <span className="auth-hint">{t("auth.min_8_chars")}</span>
          </div>
          <div>
            <label className="auth-label" htmlFor="confirm-new-password">
              {t("auth.confirm_new_password")}
            </label>
            <input
              id="confirm-new-password"
              type="password"
              className="auth-input"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              minLength={8}
              required
            />
          </div>
          {error && <p className="auth-error">{error}</p>}
          {success && <p className="auth-success-text" style={{ color: "#16a34a" }}>{success}</p>}
          <button type="submit" className="auth-button" disabled={loading}>
            {loading ? t("auth.saving") : t("auth.change_password_button")}
          </button>
        </form>

        <p className="auth-link">
          <button type="button" className="account-back-link" onClick={onBack}>
            ← {t("common.back")}
          </button>
        </p>
      </div>
    </div>
  );
}
