"use client";

import { useState, useEffect, FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

type AuthMode = "login" | "signup";

export default function LoginPage() {
  const [mode, setMode] = useState<AuthMode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [allowContact, setAllowContact] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [signupSuccess, setSignupSuccess] = useState(false);
  const router = useRouter();

  // Escape key navigates back to home (when no input is focused)
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      const activeElement = document.activeElement;
      const isInputFocused = activeElement instanceof HTMLInputElement
        || activeElement instanceof HTMLTextAreaElement;
      if (isInputFocused) return;
      router.push("/");
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [router]);

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
      setError("As senhas não coincidem");
      return;
    }

    setLoading(true);

    try {
      const endpoint = mode === "login" ? "/api/auth/login/" : "/api/auth/signup/";
      const body = mode === "login"
        ? { email, password }
        : { email, password, allow_contact: allowContact };

      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        const data = await response.json();
        if (mode === "login") {
          setError(data.error || "Email ou senha incorretos");
        } else {
          const firstError = Object.values(data).flat()[0];
          setError(String(firstError) || "Erro ao criar conta");
        }
        return;
      }

      // Both signup and login: backend sets session cookie, redirect home
      window.location.href = "/";
    } catch {
      setError("Erro de conexão. Tente novamente.");
    } finally {
      setLoading(false);
    }
  }

  if (signupSuccess) {
    return (
      <div className="auth-container">
        <div className="auth-card">
          <Link href="/" className="auth-logo-link">
            <span className="auth-logo">SPONDA</span>
          </Link>
          <h1 className="auth-title">Conta criada!</h1>
          <p className="auth-success-text">
            Sua conta foi criada e você já está logado.
          </p>
          <p className="auth-link">
            <Link href="/">Ir para a página inicial</Link>
          </p>
        </div>
      </div>
    );
  }

  const isLogin = mode === "login";

  return (
    <div className="auth-container">
      <div className="auth-card">
        <Link href="/" className="auth-logo-link">
          <span className="auth-logo">SPONDA</span>
        </Link>

        {/* Mode toggle */}
        <div className="auth-mode-toggle">
          <button
            type="button"
            className={`auth-mode-button ${isLogin ? "auth-mode-active" : ""}`}
            onClick={() => switchMode("login")}
          >
            Entrar
          </button>
          <button
            type="button"
            className={`auth-mode-button ${!isLogin ? "auth-mode-active" : ""}`}
            onClick={() => switchMode("signup")}
          >
            Criar conta
          </button>
        </div>

        <form className="auth-form" onSubmit={handleSubmit}>
          <div>
            <label className="auth-label" htmlFor="email">
              Email
            </label>
            <input
              id="email"
              type="email"
              className="auth-input"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
              autoFocus
            />
          </div>
          <div>
            <label className="auth-label" htmlFor="password">
              Senha
            </label>
            <input
              id="password"
              type="password"
              className="auth-input"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              minLength={mode === "signup" ? 8 : undefined}
              required
            />
            {!isLogin && <span className="auth-hint">Mínimo 8 caracteres</span>}
          </div>
          {!isLogin && (
            <div>
              <label className="auth-label" htmlFor="confirm-password">
                Confirmar Senha
              </label>
              <input
                id="confirm-password"
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
              Aceito receber atualizações e novidades da Sponda por email
            </label>
          )}
          {error && <p className="auth-error">{error}</p>}
          <button type="submit" className="auth-button" disabled={loading}>
            {loading
              ? (isLogin ? "Entrando…" : "Criando…")
              : (isLogin ? "Entrar" : "Criar Conta")}
          </button>
        </form>

        {isLogin && (
          <p className="auth-link">
            <Link href="/forgot-password">Esqueci minha senha</Link>
          </p>
        )}

        <div className="auth-divider">
          <span className="auth-divider-text">ou</span>
        </div>
        <GoogleSignInButton />
      </div>
    </div>
  );
}

function GoogleSignInButton() {
  function handleGoogleAuth() {
    const clientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || "";
    if (!clientId) return;

    const redirectUri = `${window.location.origin}/google/callback`;
    const scope = "openid email profile";
    const googleAuthUrl = `https://accounts.google.com/o/oauth2/v2/auth?client_id=${clientId}&redirect_uri=${encodeURIComponent(redirectUri)}&response_type=code&scope=${encodeURIComponent(scope)}&access_type=offline&prompt=consent`;

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
      Continuar com Google
    </button>
  );
}
