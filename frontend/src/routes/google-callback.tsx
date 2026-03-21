import { useEffect, useState } from "react";
import { Link } from "@tanstack/react-router";
import "../styles/auth.css";

export function GoogleCallbackPage() {
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get("code");

    if (!code) {
      setError("Código de autorização não recebido do Google.");
      return;
    }

    const redirectUri = `${window.location.origin}/google/callback`;

    fetch("/api/auth/google/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ code, redirect_uri: redirectUri }),
    })
      .then((response) => {
        if (!response.ok) {
          return response.json().then((data) => {
            throw new Error(data.error || "Erro na autenticação com Google");
          });
        }
        return response.json();
      })
      .then(() => {
        window.location.href = "/";
      })
      .catch((fetchError) => {
        setError(fetchError.message);
      });
  }, []);

  if (error) {
    return (
      <div className="auth-container">
        <div className="auth-card">
          <Link to="/" className="auth-logo-link">
            <span className="auth-logo">SPONDA</span>
          </Link>
          <h1 className="auth-title">Erro</h1>
          <p className="auth-error">{error}</p>
          <p className="auth-link">
            <Link to="/login">Tentar novamente</Link>
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-container">
      <div className="auth-card">
        <p className="auth-success-text">Autenticando com Google…</p>
      </div>
    </div>
  );
}
