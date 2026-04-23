import { useState, FormEvent } from "react";
import { useTranslation } from "../i18n";
import { setEmailVerificationPromptVisible } from "../utils/emailVerificationPrompt";
import "../styles/auth.css";
import "../styles/feedback.css";

type AuthMode = "login" | "signup";

interface AuthModalProps {
  onSuccess: () => void;
  onClose: () => void;
  message?: string;
}

export function AuthModal({ onSuccess, onClose, message }: AuthModalProps) {
  const { t, locale } = useTranslation();
  const [mode, setMode] = useState<AuthMode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [allowContact, setAllowContact] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  function switchMode(newMode: AuthMode) {
    setMode(newMode);
    setError(null);
    setPassword("");
    setConfirmPassword("");
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);

    if (mode === "signup" && password !== confirmPassword) {
      setError(t("auth.passwords_dont_match"));
      return;
    }

    setLoading(true);

    try {
      const endpoint = mode === "login" ? "/api/auth/login/" : "/api/auth/signup/";
      const body = mode === "login"
        ? { email, password }
        : { email, password, allow_contact: allowContact, language: locale };

      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        const data = await response.json();
        if (mode === "login") {
          setError(data.error || t("auth.wrong_credentials"));
        } else {
          const firstError = Object.values(data).flat()[0];
          setError(String(firstError) || t("auth.signup_error"));
        }
        return;
      }

      setEmailVerificationPromptVisible(false);
      onSuccess();
    } catch {
      setError(t("auth.connection_error"));
    } finally {
      setLoading(false);
    }
  }

  const isLogin = mode === "login";

  return (
    <div className="feedback-overlay" onClick={onClose}>
      <div className="feedback-panel" onClick={(event) => event.stopPropagation()} style={{ maxWidth: "400px" }}>
        <button className="feedback-close" onClick={onClose} aria-label={t("common.close")}>
          ×
        </button>

        {message && (
          <p className="auth-modal-message">{message}</p>
        )}

        <div className="auth-mode-toggle" style={{ marginTop: "20px", marginBottom: "1.5rem" }}>
          <button
            type="button"
            className={`auth-mode-button ${isLogin ? "auth-mode-active" : ""}`}
            onClick={() => switchMode("login")}
          >
            {t("auth.login")}
          </button>
          <button
            type="button"
            className={`auth-mode-button ${!isLogin ? "auth-mode-active" : ""}`}
            onClick={() => switchMode("signup")}
          >
            {t("auth.signup")}
          </button>
        </div>

        <form className="auth-form" onSubmit={handleSubmit}>
          <div>
            <label className="auth-label" htmlFor="modal-email">{t("auth.email")}</label>
            <input
              id="modal-email"
              type="email"
              className="auth-input"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
              autoFocus
            />
          </div>
          <div>
            <label className="auth-label" htmlFor="modal-password">{t("auth.password")}</label>
            <input
              id="modal-password"
              type="password"
              className="auth-input"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              minLength={mode === "signup" ? 8 : undefined}
              required
            />
            {!isLogin && <span className="auth-hint">{t("auth.min_8_chars")}</span>}
          </div>
          {!isLogin && (
            <div>
              <label className="auth-label" htmlFor="modal-confirm-password">{t("auth.confirm_password")}</label>
              <input
                id="modal-confirm-password"
                type="password"
                className="auth-input"
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                minLength={8}
                required
              />
            </div>
          )}
          {!isLogin && (
            <label className="auth-checkbox-label">
              <input
                type="checkbox"
                checked={allowContact}
                onChange={(event) => setAllowContact(event.target.checked)}
                className="auth-checkbox"
              />
              {t("auth.allow_contact")}
            </label>
          )}
          {error && <p className="auth-error">{error}</p>}
          <button type="submit" className="auth-button" disabled={loading}>
            {loading
              ? (isLogin ? t("auth.logging_in") : t("auth.creating"))
              : (isLogin ? t("auth.login") : t("auth.create_account"))}
          </button>
        </form>

        <div className="auth-divider">
          <span className="auth-divider-text">{t("common.or")}</span>
        </div>
        <GoogleSignInButton />
      </div>
    </div>
  );
}

function GoogleSignInButton() {
  const { t, locale } = useTranslation();

  function handleGoogleAuth() {
    const clientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || "";
    if (!clientId) return;

    const redirectUri = `${window.location.origin}/google/callback`;
    const scope = "openid email profile";
    const googleAuthUrl = `https://accounts.google.com/o/oauth2/v2/auth?client_id=${clientId}&redirect_uri=${encodeURIComponent(redirectUri)}&response_type=code&scope=${encodeURIComponent(scope)}&access_type=offline&prompt=consent&state=${locale}`;

    window.location.href = googleAuthUrl;
  }

  return (
    <button
      type="button"
      className="auth-button-secondary"
      onClick={handleGoogleAuth}
      style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "0.5rem" }}
    >
      <svg className="auth-google-icon" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
        <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4"/>
        <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
        <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
        <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
      </svg>
      {t("auth.continue_with_google")}
    </button>
  );
}
