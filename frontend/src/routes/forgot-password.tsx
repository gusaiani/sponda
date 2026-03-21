import { useState, FormEvent } from "react";
import { Link } from "@tanstack/react-router";
import "../styles/auth.css";

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);

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
        setError(data.error || "Erro ao enviar email");
        return;
      }

      setSent(true);
    } catch {
      setError("Erro de conexão. Tente novamente.");
    } finally {
      setLoading(false);
    }
  }

  if (sent) {
    return (
      <div className="auth-container">
        <div className="auth-card">
          <Link to="/" className="auth-logo-link">
            <span className="auth-logo">SPONDA</span>
          </Link>
          <h1 className="auth-title">Email enviado</h1>
          <p className="auth-success-text">
            Se existe uma conta com esse email, você receberá um link para
            redefinir sua senha.
          </p>
          <p className="auth-link">
            <Link to="/login">Voltar para login</Link>
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
        <h1 className="auth-title">Recuperar Senha</h1>
        <p className="auth-success-text">
          Digite seu email e enviaremos um link para redefinir sua senha.
        </p>
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
              onChange={(e) => setEmail(e.target.value)}
              required
              autoFocus
            />
          </div>
          {error && <p className="auth-error">{error}</p>}
          <button type="submit" className="auth-button" disabled={loading}>
            {loading ? "Enviando…" : "Enviar link de recuperação"}
          </button>
        </form>
        <p className="auth-link">
          <Link to="/login">Voltar para login</Link>
        </p>
      </div>
    </div>
  );
}
