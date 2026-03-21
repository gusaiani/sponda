import { useState, FormEvent } from "react";
import { Link } from "@tanstack/react-router";
import "../styles/auth.css";

export function ResetPasswordPage() {
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  // Extract token from URL query params
  const params = new URLSearchParams(window.location.search);
  const token = params.get("token") ?? "";

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);

    if (password !== confirmPassword) {
      setError("As senhas não coincidem");
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
        setError(data.error || "Erro ao redefinir senha");
        return;
      }

      setSuccess(true);
    } catch {
      setError("Erro de conexão. Tente novamente.");
    } finally {
      setLoading(false);
    }
  }

  if (!token) {
    return (
      <div className="auth-container">
        <div className="auth-card">
          <Link to="/" className="auth-logo-link">
            <span className="auth-logo">SPONDA</span>
          </Link>
          <h1 className="auth-title">Link inválido</h1>
          <p className="auth-success-text">
            Este link de recuperação é inválido ou expirou.
          </p>
          <p className="auth-link">
            <Link to="/forgot-password">Solicitar novo link</Link>
          </p>
        </div>
      </div>
    );
  }

  if (success) {
    return (
      <div className="auth-container">
        <div className="auth-card">
          <Link to="/" className="auth-logo-link">
            <span className="auth-logo">SPONDA</span>
          </Link>
          <h1 className="auth-title">Senha redefinida!</h1>
          <p className="auth-success-text">
            Sua senha foi alterada com sucesso.
          </p>
          <p className="auth-link">
            <Link to="/login">Fazer login</Link>
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-container">
      <div className="auth-card">
        <Link to="/" className="auth-logo-link">
          <span className="auth-logo">SPONDA</span>
        </Link>
        <h1 className="auth-title">Nova Senha</h1>
        <form className="auth-form" onSubmit={handleSubmit}>
          <div>
            <label className="auth-label" htmlFor="password">
              Nova senha
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
            <span className="auth-hint">Mínimo 8 caracteres</span>
          </div>
          <div>
            <label className="auth-label" htmlFor="confirm-password">
              Confirmar nova senha
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
            {loading ? "Salvando…" : "Redefinir senha"}
          </button>
        </form>
      </div>
    </div>
  );
}
