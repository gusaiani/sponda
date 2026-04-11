"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { isSupportedLocale, DEFAULT_LOCALE } from "../../../lib/i18n-config";

export function GoogleCallbackContent() {
  const searchParams = useSearchParams();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const code = searchParams.get("code");

    if (!code) {
      setError("No authorization code received from Google.");
      return;
    }

    const stateLocale = searchParams.get("state") || "";
    const locale = isSupportedLocale(stateLocale) ? stateLocale : DEFAULT_LOCALE;
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
            throw new Error(data.error || "Google authentication failed");
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
          <span className="auth-logo">SPONDA</span>
          <h1 className="auth-title">Error</h1>
          <p className="auth-error">{error}</p>
          <p className="auth-link">
            <a href="/en/login">Try again</a>
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-container">
      <div className="auth-card">
        <p className="auth-success-text">Authenticating with Google...</p>
      </div>
    </div>
  );
}
