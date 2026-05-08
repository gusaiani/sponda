"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { useAuth } from "../hooks/useAuth";
import { useTranslation } from "../i18n";
import { csrfHeaders } from "../utils/csrf";

const POLL_INTERVAL_MS = 3000;

type PendingAction = () => void | Promise<void>;

interface VerificationContextValue {
  /** Wraps an action so it only runs once the user is verified. If the
   *  user is already verified, runs immediately. Otherwise stashes the
   *  action and opens the modal; the action fires automatically when
   *  the auth poll detects verification. */
  requireVerification: (action: PendingAction) => void;
}

const VerificationContext = createContext<VerificationContextValue | null>(null);

export function useEmailVerification(): VerificationContextValue {
  const ctx = useContext(VerificationContext);
  if (!ctx) {
    // Outside of the provider (e.g. in tests) — passthrough.
    return { requireVerification: (action) => { void action(); } };
  }
  return ctx;
}


export function EmailVerificationProvider({ children }: { children: React.ReactNode }) {
  const { user, isAuthenticated, refreshUser } = useAuth();
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const [resendState, setResendState] = useState<"idle" | "sending" | "sent" | "error">("idle");
  const pendingActionRef = useRef<PendingAction | null>(null);

  const requireVerification = useCallback((action: PendingAction) => {
    if (isAuthenticated && user?.email_verified) {
      void action();
      return;
    }
    pendingActionRef.current = action;
    setResendState("idle");
    setIsOpen(true);
  }, [isAuthenticated, user?.email_verified]);

  // Poll auth-user while the modal is open so we pick up verification
  // performed in another tab / via the email link without requiring a
  // page reload. Cheap enough at 3s — single GET /api/auth/me/ that's
  // already cached and revalidates once verified.
  useEffect(() => {
    if (!isOpen) return;
    const timer = window.setInterval(() => { void refreshUser(); }, POLL_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [isOpen, refreshUser]);

  // Replay the pending action the moment verification flips true.
  useEffect(() => {
    if (!isOpen) return;
    if (!user?.email_verified) return;
    const action = pendingActionRef.current;
    pendingActionRef.current = null;
    setIsOpen(false);
    if (action) void action();
  }, [isOpen, user?.email_verified]);

  function close() {
    pendingActionRef.current = null;
    setIsOpen(false);
  }

  async function resend() {
    setResendState("sending");
    try {
      const response = await fetch("/api/auth/resend-verification/", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json", ...csrfHeaders() },
      });
      setResendState(response.ok ? "sent" : "error");
    } catch {
      setResendState("error");
    }
  }

  return (
    <VerificationContext.Provider value={{ requireVerification }}>
      {children}
      {isOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="verification-modal-title"
          onClick={(e) => { if (e.target === e.currentTarget) close(); }}
          style={{
            position: "fixed", inset: 0, zIndex: 1000,
            background: "rgba(0,0,0,0.4)",
            display: "flex", alignItems: "center", justifyContent: "center",
            padding: "16px",
          }}
        >
          <div
            style={{
              background: "#fff", borderRadius: "12px", padding: "24px",
              maxWidth: "440px", width: "100%",
              boxShadow: "0 16px 48px rgba(0, 0, 0, 0.2)",
            }}
          >
            <h2 id="verification-modal-title" style={{ margin: "0 0 8px", fontSize: "20px", color: "#1b347e" }}>
              {t("social.verification_modal.title")}
            </h2>
            <p style={{ margin: "0 0 12px", color: "#222" }}>
              {t("social.verification_modal.body")}
            </p>
            <p style={{ margin: "0 0 20px", color: "#666", fontSize: "13px" }}>
              {t("social.verification_modal.help", { email: user?.email ?? "" })}
            </p>
            <p style={{ margin: "0 0 16px", color: "#888", fontSize: "12px", fontStyle: "italic" }}>
              {t("social.verification_modal.waiting")}
            </p>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px" }}>
              <button
                type="button"
                onClick={close}
                style={{ padding: "8px 14px", border: "1px solid #ccc", borderRadius: "6px", background: "#fff", cursor: "pointer" }}
              >
                {t("common.close")}
              </button>
              <button
                type="button"
                onClick={resend}
                disabled={resendState === "sending"}
                style={{
                  padding: "8px 16px", border: "none", borderRadius: "6px",
                  background: resendState === "sent" ? "#16a34a" : "#1b347e",
                  color: "#fff", fontWeight: 600,
                  cursor: resendState === "sending" ? "wait" : "pointer",
                }}
              >
                {resendState === "sending" ? t("common.loading")
                  : resendState === "sent" ? t("social.verification_modal.resent")
                  : resendState === "error" ? t("social.verification_modal.resend")
                  : t("social.verification_modal.resend")}
              </button>
            </div>
          </div>
        </div>
      )}
    </VerificationContext.Provider>
  );
}
