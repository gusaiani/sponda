import { useState, FormEvent } from "react";
import { Link } from "@tanstack/react-router";
import { useAuth } from "../hooks/useAuth";
import "../styles/auth.css";

export function AccountPage() {
  const { user, isLoading, isAuthenticated, logout } = useAuth();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (isLoading) {
    return (
      <div className="auth-container">
        <div className="auth-card">
          <p className="auth-success-text">Carregando…</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="auth-container">
        <div className="auth-card">
          <Link to="/" className="auth-logo-link">
            <span className="auth-logo">SPONDA</span>
          </Link>
          <h1 className="auth-title">Acesso restrito</h1>
          <p className="auth-success-text">
            Você precisa estar logado para acessar esta página.
          </p>
          <p className="auth-link">
            <Link to="/login">Fazer login</Link>
          </p>
        </div>
      </div>
    );
  }

  async function handleChangePassword(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    if (newPassword !== confirmPassword) {
      setError("As senhas não coincidem");
      return;
    }

    setLoading(true);

    try {
      const response = await fetch("/api/auth/change-password/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      });

      if (!response.ok) {
        const data = await response.json();
        setError(data.error || "Erro ao alterar senha");
        return;
      }

      setSuccess("Senha alterada com sucesso!");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch {
      setError("Erro de conexão. Tente novamente.");
    } finally {
      setLoading(false);
    }
  }

  async function handleLogout() {
    await logout();
    window.location.href = "/";
  }

  return (
    <div className="auth-container">
      <div className="auth-card">
        <Link to="/" className="auth-logo-link">
          <span className="auth-logo">SPONDA</span>
        </Link>
        <h1 className="auth-title">Minha Conta</h1>

        <p className="auth-success-text">{user?.email}</p>

        <h2 className="auth-title" style={{ fontSize: "1.1rem", marginTop: "2rem" }}>
          Alterar Senha
        </h2>
        <form className="auth-form" onSubmit={handleChangePassword}>
          <div>
            <label className="auth-label" htmlFor="current-password">
              Senha atual
            </label>
            <input
              id="current-password"
              type="password"
              className="auth-input"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              required
            />
          </div>
          <div>
            <label className="auth-label" htmlFor="new-password">
              Nova senha
            </label>
            <input
              id="new-password"
              type="password"
              className="auth-input"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              minLength={8}
              required
            />
            <span className="auth-hint">Mínimo 8 caracteres</span>
          </div>
          <div>
            <label className="auth-label" htmlFor="confirm-new-password">
              Confirmar nova senha
            </label>
            <input
              id="confirm-new-password"
              type="password"
              className="auth-input"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              minLength={8}
              required
            />
          </div>
          {error && <p className="auth-error">{error}</p>}
          {success && <p className="auth-success-text" style={{ color: "#16a34a" }}>{success}</p>}
          <button type="submit" className="auth-button" disabled={loading}>
            {loading ? "Salvando…" : "Alterar senha"}
          </button>
        </form>

        <div style={{ marginTop: "2rem" }}>
          <button
            type="button"
            className="auth-button-secondary"
            onClick={handleLogout}
          >
            Sair da conta
          </button>
        </div>

        <p className="auth-link">
          <Link to="/">Voltar para a página inicial</Link>
        </p>
      </div>
    </div>
  );
}
