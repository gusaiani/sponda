"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useTranslation } from "../../../../i18n";

function GoogleCallbackContent() {
  const searchParams = useSearchParams();
  const { locale } = useTranslation();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const code = searchParams.get("code");

    if (!code) {
      setError("Código de autorização não recebido do Google.");
      return;
    }

    const redirectUri = `${window.location.origin}/${locale}/google/callback`;

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
        window.location.href = `/${locale}`;
      })
      .catch((fetchError) => {
        setError(fetchError.message);
      });
  }, [searchParams]);

  if (error) {
    return (
      <div className="auth-container">
        <div className="auth-card">
          <Link href={`/${locale}`} className="auth-logo-link">
            <span className="auth-logo">SPONDA</span>
          </Link>
          <h1 className="auth-title">Erro</h1>
          <p className="auth-error">{error}</p>
          <p className="auth-link">
            <Link href={`/${locale}/login`}>Tentar novamente</Link>
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

export default function GoogleCallbackPage() {
  return (
    <Suspense fallback={<div className="auth-container"><div className="auth-card"><p className="auth-success-text">Carregando…</p></div></div>}>
      <GoogleCallbackContent />
    </Suspense>
  );
}
