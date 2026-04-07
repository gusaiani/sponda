"use client";

import { Suspense, useState, FormEvent } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useTranslation } from "../../../i18n";

export default function ResetPasswordPage() {
  const { t } = useTranslation();
  return (
    <Suspense fallback={<div className="auth-container"><div className="auth-card"><p className="auth-success-text">{t("common.loading")}</p></div></div>}>
      <ResetPasswordContent />
    </Suspense>
  );
}

function ResetPasswordContent() {
  const { t, locale } = useTranslation();
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);

    if (password !== confirmPassword) {
      setError(t("auth.passwords_dont_match"));
      return;
    }

    setLoading(true);

    try {
      const response = await fetch("/api/auth/reset-password/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, password }),
      });

      if (!response.ok) {
        const data = await response.json();
        setError(data.error || t("reset.error"));
        return;
      }

      setSuccess(true);
    } catch {
      setError(t("auth.connection_error"));
    } finally {
      setLoading(false);
    }
  }

  if (!token) {
    return (
      <div className="auth-container">
        <div className="auth-card">
          <Link href={`/${locale}`} className="auth-logo-link">
            <span className="auth-logo">SPONDA</span>
          </Link>
          <h1 className="auth-title">{t("reset.invalid_link")}</h1>
          <p className="auth-success-text">
            {t("reset.invalid_link_text")}
          </p>
          <p className="auth-link">
            <Link href={`/${locale}/forgot-password`}>{t("reset.request_new_link")}</Link>
          </p>
        </div>
      </div>
    );
  }

  if (success) {
    return (
      <div className="auth-container">
        <div className="auth-card">
          <Link href={`/${locale}`} className="auth-logo-link">
            <span className="auth-logo">SPONDA</span>
          </Link>
          <h1 className="auth-title">{t("reset.success_title")}</h1>
          <p className="auth-success-text">
            {t("reset.success_text")}
          </p>
          <p className="auth-link">
            <Link href={`/${locale}/login`}>{t("auth.do_login")}</Link>
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-container">
      <div className="auth-card">
        <Link href={`/${locale}`} className="auth-logo-link">
          <span className="auth-logo">SPONDA</span>
        </Link>
        <h1 className="auth-title">{t("reset.title")}</h1>
        <form className="auth-form" onSubmit={handleSubmit}>
          <div>
            <label className="auth-label" htmlFor="password">
              {t("reset.new_password")}
            </label>
            <input
              id="password"
              type="password"
              className="auth-input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              minLength={8}
              required
              autoFocus
            />
            <span className="auth-hint">{t("auth.min_8_chars")}</span>
          </div>
          <div>
            <label className="auth-label" htmlFor="confirm-password">
              {t("reset.confirm_new_password")}
            </label>
            <input
              id="confirm-password"
              type="password"
              className="auth-input"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              minLength={8}
              required
            />
          </div>
          {error && <p className="auth-error">{error}</p>}
          <button type="submit" className="auth-button" disabled={loading}>
            {loading ? t("reset.saving") : t("reset.submit")}
          </button>
        </form>
      </div>
    </div>
  );
}
