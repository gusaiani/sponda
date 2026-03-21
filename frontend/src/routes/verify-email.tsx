import { useEffect, useState } from "react";
import { Link } from "@tanstack/react-router";
import "../styles/auth.css";

export function VerifyEmailPage() {
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get("token");

    if (!token) {
      setStatus("error");
      setErrorMessage("Link inválido — token não encontrado.");
      return;
    }

    fetch("/api/auth/verify-email/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ token }),
    })
      .then((response) => {
        if (!response.ok) {
          return response.json().then((data) => {
            throw new Error(data.error || "Erro ao verificar email");
          });
        }
        setStatus("success");
      })
      .catch((fetchError) => {
        setStatus("error");
        setErrorMessage(fetchError.message);
      });
  }, []);

  return (
    <div className="auth-container">
      <div className="auth-card">
        <Link to="/" className="auth-logo-link">
          <span className="auth-logo">SPONDA</span>
        </Link>

        {status === "loading" && (
          <p className="auth-success-text">Verificando...</p>
        )}

        {status === "success" && (
          <>
            <h1 className="auth-title">Email verificado!</h1>
            <p className="auth-success-text">
              Seu email foi confirmado. Todas as funcionalidades estão ativas.
            </p>
            <p className="auth-link">
              <Link to="/">Ir para a página inicial</Link>
            </p>
          </>
        )}

        {status === "error" && (
          <>
            <h1 className="auth-title">Link inválido</h1>
            <p className="auth-error" style={{ marginBottom: "1rem" }}>
              {errorMessage}
            </p>
            <p className="auth-success-text">
              O link pode ter expirado. Solicite um novo na sua conta.
            </p>
            <p className="auth-link">
              <Link to="/account">Minha conta</Link>
            </p>
          </>
        )}
      </div>
    </div>
  );
}
