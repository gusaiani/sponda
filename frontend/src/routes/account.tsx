import { useState, FormEvent } from "react";
import { Link } from "@tanstack/react-router";
import { useAuth } from "../hooks/useAuth";
import { csrfHeaders } from "../utils/csrf";
import "../styles/auth.css";

function formatTimeSince(dateString: string): string {
  const joined = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - joined.getTime();

  const minutes = Math.floor(diffMs / (1000 * 60));
  const hours = Math.floor(diffMs / (1000 * 60 * 60));
  const days = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  const months = Math.floor(days / 30);
  const years = Math.floor(days / 365);

  if (years > 0) return `${years} ${years === 1 ? "ano" : "anos"}`;
  if (months > 0) return `${months} ${months === 1 ? "mês" : "meses"}`;
  if (days > 0) return `${days} ${days === 1 ? "dia" : "dias"}`;
  if (hours > 0) return `${hours} ${hours === 1 ? "hora" : "horas"}`;
  return `${minutes} ${minutes === 1 ? "minuto" : "minutos"}`;
}

function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "long",
    year: "numeric",
  });
}

type AccountView = "main" | "change-password";

export function AccountPage() {
  const { user, isLoading, isAuthenticated, logout } = useAuth();
  const [view, setView] = useState<AccountView>("main");

  if (isLoading) {
    return (
      <div className="auth-container">
        <div className="auth-card">
          <p className="auth-success-text">Carregando…</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated || !user) {
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

  async function handleLogout() {
    await logout();
    window.location.href = "/";
  }

  if (view === "change-password") {
    return (
      <ChangePasswordView
        onBack={() => setView("main")}
      />
    );
  }

  return (
    <div className="auth-container">
      <div className="auth-card">
        <Link to="/" className="auth-logo-link">
          <span className="auth-logo">SPONDA</span>
        </Link>
        <h1 className="auth-title">Minha Conta</h1>

        <p className="account-membership">
          Você faz parte da Sponda desde{" "}
          <strong>{formatDate(user.date_joined)}</strong>
          {" "}— há {formatTimeSince(user.date_joined)}.
        </p>

        <div className="account-actions">
          <button
            type="button"
            className="account-action-link"
            onClick={() => setView("change-password")}
          >
            Trocar senha
          </button>
          <button
            type="button"
            className="account-action-link"
            onClick={handleLogout}
          >
            Fazer logout
          </button>
        </div>

        <p className="auth-link">
          <Link to="/">Voltar para a página inicial</Link>
        </p>
      </div>
    </div>
  );
}

function ChangePasswordView({ onBack }: { onBack: () => void }) {
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
      setError("As senhas não coincidem");
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

  return (
    <div className="auth-container">
      <div className="auth-card">
        <Link to="/" className="auth-logo-link">
          <span className="auth-logo">SPONDA</span>
        </Link>
        <h1 className="auth-title">Trocar Senha</h1>

        <form className="auth-form" onSubmit={handleSubmit}>
          <div>
            <label className="auth-label" htmlFor="current-password">
              Senha atual
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
              Nova senha
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
              onChange={(event) => setConfirmPassword(event.target.value)}
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

        <p className="auth-link">
          <button type="button" className="account-back-link" onClick={onBack}>
            ← Voltar
          </button>
        </p>
      </div>
    </div>
  );
}
