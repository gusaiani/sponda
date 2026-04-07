"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
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
  const searchParams = useSearchParams();
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    const token = searchParams.get("token");

    if (!token) {
      setStatus("error");
      setErrorMessage(t("verify.invalid_token"));
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
            throw new Error(data.error || t("verify.error"));
          });
        }
        setStatus("success");
      })
      .catch((fetchError) => {
        setStatus("error");
        setErrorMessage(fetchError.message);
      });
  }, [searchParams, t]);

  return (
    <div className="auth-container">
      <div className="auth-card">
        <Link href={`/${locale}`} className="auth-logo-link">
          <span className="auth-logo">SPONDA</span>
        </Link>

        {status === "loading" && (
          <p className="auth-success-text">{t("verify.verifying")}</p>
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
