"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { useAuth } from "../../../hooks/useAuth";
import { csrfHeaders } from "../../../utils/csrf";
import { useTranslation } from "../../../i18n";

export default function VerifyEmailPage() {
  const { t } = useTranslation();
  return (
    <Suspense fallback={<div className="auth-container"><div className="auth-card"><p className="auth-success-text">{t("common.loading")}</p></div></div>}>
      <VerifyEmailContent />
    </Suspense>
  );
}

function VerifyEmailContent() {
  const { t, locale } = useTranslation();
  const queryClient = useQueryClient();
  const { user, isLoading, isAuthenticated } = useAuth();
  const searchParams = useSearchParams();
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [errorMessage, setErrorMessage] = useState("");
  const [resendStatus, setResendStatus] = useState<"idle" | "sending" | "sent" | "error">("idle");

  useEffect(() => {
    const token = searchParams.get("token");

    if (!token) {
      setStatus("idle");
      setErrorMessage("");
      return;
    }

    setStatus("loading");
    fetch("/api/auth/verify-email/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ token }),
    })
      .then((response) => {
        if (!response.ok) {
          return response.json().then((data) => {
            throw new Error(data.error || t("verify.error"));
          });
        }
        queryClient.invalidateQueries({ queryKey: ["auth-user"] });
        setStatus("success");
      })
      .catch((fetchError) => {
        setStatus("error");
        setErrorMessage(fetchError.message);
      });
  }, [queryClient, searchParams, t]);

  async function handleResend() {
    setResendStatus("sending");
    try {
      const response = await fetch("/api/auth/resend-verification/", {
        method: "POST",
        headers: csrfHeaders(),
        credentials: "include",
      });
      if (!response.ok) {
        setResendStatus("error");
        return;
      }
      setResendStatus("sent");
    } catch {
      setResendStatus("error");
    }
  }

  return (
    <div className="auth-container">
      <div className="auth-card">
        <Link href={`/${locale}`} className="auth-logo-link">
          <span className="auth-logo">SPONDA</span>
        </Link>

        {status === "loading" && (
          <p className="auth-success-text">{t("verify.verifying")}</p>
        )}

        {status === "idle" && !isLoading && isAuthenticated && user && !user.email_verified && (
          <>
            <h1 className="auth-title">{t("verify.pending_title")}</h1>
            <p className="auth-success-text">
              {t("verify.pending_text")}
            </p>
            <div className="account-verification" style={{ marginTop: "1.5rem", marginBottom: "1.5rem" }}>
              <p className="account-verification-note">{t("auth.email_not_verified_note")}</p>
              <button
                type="button"
                className="account-action-link"
                onClick={handleResend}
                disabled={resendStatus === "sending" || resendStatus === "sent"}
              >
                {resendStatus === "sending"
                  ? t("auth.resend_verification_sending")
                  : t("auth.resend_verification")}
              </button>
              {resendStatus === "sent" && (
                <p className="auth-success-text" style={{ color: "#16a34a" }}>
                  {t("auth.resend_verification_sent")}
                </p>
              )}
              {resendStatus === "error" && (
                <p className="auth-error">{t("auth.resend_verification_error")}</p>
              )}
            </div>
            <p className="auth-link">
              <Link href={`/${locale}/account`}>{t("auth.my_account")}</Link>
            </p>
          </>
        )}

        {status === "idle" && !isLoading && (!isAuthenticated || !user || user.email_verified) && (
          <>
            <h1 className="auth-title">{t("verify.invalid_link")}</h1>
            <p className="auth-success-text">
              {t("verify.invalid_token")}
            </p>
            <p className="auth-link">
              <Link href={isAuthenticated ? `/${locale}/account` : `/${locale}/login`}>
                {isAuthenticated ? t("auth.my_account") : t("auth.do_login")}
              </Link>
            </p>
          </>
        )}

        {status === "success" && (
          <>
            <h1 className="auth-title">{t("verify.success_title")}</h1>
            <p className="auth-success-text">
              {t("verify.success_text")}
            </p>
            <p className="auth-link">
              <Link href={`/${locale}`}>{t("auth.go_to_homepage")}</Link>
            </p>
          </>
        )}

        {status === "error" && (
          <>
            <h1 className="auth-title">{t("verify.invalid_link")}</h1>
            <p className="auth-error" style={{ marginBottom: "1rem" }}>
              {errorMessage}
            </p>
            <p className="auth-success-text">
              {t("verify.expired_text")}
            </p>
            <p className="auth-link">
              <Link href={`/${locale}/account`}>{t("auth.my_account")}</Link>
            </p>
          </>
        )}
      </div>
    </div>
  );
}
