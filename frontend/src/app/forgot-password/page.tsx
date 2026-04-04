"use client";

import { useState, FormEvent } from "react";
import Link from "next/link";
import { useTranslation } from "../../i18n";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const { t } = useTranslation();

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const response = await fetch("/api/auth/forgot-password/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });

      if (!response.ok) {
        const data = await response.json();
        setError(data.error || t("forgot.send_error"));
        return;
      }

      setSent(true);
    } catch {
      setError(t("auth.connection_error"));
    } finally {
      setLoading(false);
    }
  }

  if (sent) {
    return (
      <div className="auth-container">
        <div className="auth-card">
          <Link href="/" className="auth-logo-link">
            <span className="auth-logo">SPONDA</span>
          </Link>
          <h1 className="auth-title">{t("forgot.email_sent")}</h1>
          <p className="auth-success-text">
            {t("forgot.email_sent_text")}
          </p>
          <p className="auth-link">
            <Link href="/login">{t("forgot.back_to_login")}</Link>
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-container">
      <div className="auth-card">
        <Link href="/" className="auth-logo-link">
          <span className="auth-logo">SPONDA</span>
        </Link>
        <h1 className="auth-title">{t("forgot.title")}</h1>
        <p className="auth-success-text">
          {t("forgot.description")}
        </p>
        <form className="auth-form" onSubmit={handleSubmit}>
          <div>
            <label className="auth-label" htmlFor="email">
              {t("auth.email")}
            </label>
            <input
              id="email"
              type="email"
              className="auth-input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoFocus
            />
          </div>
          {error && <p className="auth-error">{error}</p>}
          <button type="submit" className="auth-button" disabled={loading}>
            {loading ? t("forgot.sending") : t("forgot.send_link")}
          </button>
        </form>
        <p className="auth-link">
          <Link href="/login">{t("forgot.back_to_login")}</Link>
        </p>
      </div>
    </div>
  );
}
