"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={<div className="auth-container"><div className="auth-card"><p className="auth-success-text">Carregando…</p></div></div>}>
      <VerifyEmailContent />
    </Suspense>
  );
}

function VerifyEmailContent() {
  const searchParams = useSearchParams();
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    const token = searchParams.get("token");

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
  }, [searchParams]);

  return (
    <div className="auth-container">
      <div className="auth-card">
        <Link href="/" className="auth-logo-link">
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
              <Link href="/">Ir para a página inicial</Link>
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
              <Link href="/account">Minha conta</Link>
            </p>
          </>
        )}
      </div>
    </div>
  );
}
