"use client";

import { useEffect, useState, FormEvent } from "react";
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

type AccountView = "main" | "change-password" | "change-email" | "delete-account";

export default function AccountPage() {
  const { user, isLoading, isAuthenticated, logout, refreshUser } = useAuth();
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

  if (view === "change-email") {
    return (
      <ChangeEmailView
        currentEmail={user.email}
        onBack={() => setView("main")}
        refreshUser={refreshUser}
      />
    );
  }

  if (view === "delete-account") {
    return (
      <DeleteAccountView
        email={user.email}
        onBack={() => setView("main")}
      />
    );
  }

  return (
    <div className="auth-container">
      <div className="auth-card">
        <h1 className="auth-title">{t("auth.my_account")}</h1>

        <p className="account-membership">
          {t("auth.member_since")}<br/>
          <strong>{formatDate(user.date_joined, locale)}.</strong>
        </p>

        <div className="account-actions">
          <button
            type="button"
            className="account-action-link"
            onClick={() => setView("change-email")}
          >
            {t("auth.change_email")}
          </button>
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
          <button
            type="button"
            className="account-action-link account-action-danger"
            onClick={() => setView("delete-account")}
          >
            {t("auth.delete_account")}
          </button>
        </div>

        {!user.email_verified && <EmailVerificationSection />}

        <PreferencesSection allowContact={user.allow_contact} />


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

function ChangeEmailView({
  currentEmail,
  onBack,
  refreshUser,
}: {
  currentEmail: string;
  onBack: () => void;
  refreshUser: () => Promise<void> | void;
}) {
  const { t, locale } = useTranslation();
  const [newEmail, setNewEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSuccess(null);
    setLoading(true);

    try {
      const response = await fetch("/api/auth/change-email/", {
        method: "POST",
        headers: csrfHeaders(),
        credentials: "include",
        body: JSON.stringify({
          new_email: newEmail.trim(),
          password,
        }),
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        setError(data.error || t("auth.change_email_error"));
        return;
      }

      setSuccess(t("auth.change_email_verification_sent"));
      setPassword("");
      await refreshUser();
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
        <h1 className="auth-title">{t("auth.change_email_title")}</h1>

        <p className="account-membership">
          {currentEmail}
        </p>

        <form className="auth-form" onSubmit={handleSubmit}>
          <div>
            <label className="auth-label" htmlFor="change-email-new">
              {t("auth.new_email")}
            </label>
            <input
              id="change-email-new"
              type="email"
              className="auth-input"
              value={newEmail}
              onChange={(event) => setNewEmail(event.target.value)}
              autoComplete="off"
              required
              autoFocus
            />
          </div>
          <div>
            <label className="auth-label" htmlFor="change-email-password">
              {t("auth.current_password")}
            </label>
            <input
              id="change-email-password"
              type="password"
              className="auth-input"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
              required
            />
          </div>
          {error && <p className="auth-error">{error}</p>}
          {success && (
            <p className="auth-success-text" style={{ color: "#16a34a" }}>
              {success}
            </p>
          )}
          <button type="submit" className="auth-button" disabled={loading}>
            {loading ? t("auth.saving") : t("auth.change_email_button")}
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

type ResendStatus = "idle" | "sending" | "sent" | "error";

function EmailVerificationSection() {
  const { t } = useTranslation();
  const [status, setStatus] = useState<ResendStatus>("idle");

  async function handleResend() {
    setStatus("sending");
    try {
      const response = await fetch("/api/auth/resend-verification/", {
        method: "POST",
        headers: csrfHeaders(),
        credentials: "include",
      });
      if (!response.ok) {
        setStatus("error");
        return;
      }
      setStatus("sent");
    } catch {
      setStatus("error");
    }
  }

  return (
    <div className="account-verification">
      <p className="account-verification-note">{t("auth.email_not_verified_note")}</p>
      <button
        type="button"
        className="account-action-link"
        onClick={handleResend}
        disabled={status === "sending" || status === "sent"}
      >
        {status === "sending"
          ? t("auth.resend_verification_sending")
          : t("auth.resend_verification")}
      </button>
      {status === "sent" && (
        <p className="auth-success-text" style={{ color: "#16a34a" }}>
          {t("auth.resend_verification_sent")}
        </p>
      )}
      {status === "error" && (
        <p className="auth-error">{t("auth.resend_verification_error")}</p>
      )}
    </div>
  );
}

type PreferencesStatus = "idle" | "saving" | "saved" | "error";

const SAVED_INDICATOR_DURATION_MS = 2000;

function PreferencesSection({ allowContact }: { allowContact: boolean }) {
  const { t } = useTranslation();
  const [checked, setChecked] = useState(allowContact);
  const [status, setStatus] = useState<PreferencesStatus>("idle");

  useEffect(() => {
    if (status !== "saved") return;
    const timer = setTimeout(() => setStatus("idle"), SAVED_INDICATOR_DURATION_MS);
    return () => clearTimeout(timer);
  }, [status]);

  async function handleToggle(event: React.ChangeEvent<HTMLInputElement>) {
    const next = event.target.checked;
    const previous = checked;
    setChecked(next);
    setStatus("saving");

    try {
      const response = await fetch("/api/auth/preferences/", {
        method: "PATCH",
        headers: csrfHeaders(),
        credentials: "include",
        body: JSON.stringify({ allow_contact: next }),
      });

      if (!response.ok) {
        setChecked(previous);
        setStatus("error");
        return;
      }

      setStatus("saved");
    } catch {
      setChecked(previous);
      setStatus("error");
    }
  }

  return (
    <div className="account-preferences">
      <label className="auth-checkbox-label">
        <input
          type="checkbox"
          className="auth-checkbox"
          checked={checked}
          onChange={handleToggle}
          disabled={status === "saving"}
        />
        {t("auth.allow_contact")}
      </label>
      {status === "saving" && (
        <p className="account-preferences-status">{t("auth.preferences_saving")}</p>
      )}
      {status === "saved" && (
        <p className="account-preferences-status account-preferences-status-saved">
          <span aria-hidden="true">✓ </span>
          <span>{t("auth.preferences_saved")}</span>
        </p>
      )}
      {status === "error" && (
        <p className="auth-error">{t("auth.preferences_update_error")}</p>
      )}
    </div>
  );
}

function DeleteAccountView({ email, onBack }: { email: string; onBack: () => void }) {
  const { t, locale } = useTranslation();
  const [typedEmail, setTypedEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const matches = typedEmail.trim().toLowerCase() === email.trim().toLowerCase();

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);

    if (!matches) {
      setError(t("auth.delete_account_email_mismatch"));
      return;
    }

    setLoading(true);

    try {
      const response = await fetch("/api/auth/delete-account/", {
        method: "DELETE",
        headers: csrfHeaders(),
        credentials: "include",
        body: JSON.stringify({ email_confirmation: typedEmail.trim() }),
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        setError(data.error || t("auth.delete_account_error"));
        setLoading(false);
        return;
      }

      window.location.href = `/${locale}`;
    } catch {
      setError(t("auth.connection_error"));
      setLoading(false);
    }
  }

  return (
    <div className="auth-container">
      <div className="auth-card">
        <Link href={`/${locale}`} className="auth-logo-link">
          <span className="auth-logo">SPONDA</span>
        </Link>
        <h1 className="auth-title">{t("auth.delete_account_title")}</h1>

        <p className="account-delete-warning">{t("auth.delete_account_warning")}</p>

        <form className="auth-form" onSubmit={handleSubmit}>
          <div>
            <label className="auth-label" htmlFor="delete-account-email">
              {t("auth.delete_account_type_email")}
            </label>
            <input
              id="delete-account-email"
              type="email"
              className="auth-input"
              value={typedEmail}
              onChange={(event) => setTypedEmail(event.target.value)}
              autoComplete="off"
              autoFocus
              required
            />
          </div>
          {error && <p className="auth-error">{error}</p>}
          <button
            type="submit"
            className="auth-button auth-button-danger"
            disabled={loading || !matches}
          >
            {loading ? t("auth.deleting") : t("auth.delete_account_button")}
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
