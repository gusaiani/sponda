"use client";

import { useEffect, useRef, useState } from "react";
import { useAuth } from "../hooks/useAuth";
import { useAlerts } from "../hooks/useAlerts";
import { useTranslation } from "../i18n";
import { AuthModal } from "./AuthModal";
import "../styles/alert-button.css";

interface AlertButtonProps {
  ticker: string;
  /** Backend indicator key (e.g. "pe10", "debt_to_equity"). */
  indicator: string;
  /** Label shown in the popover header so the user knows what they're alerting on. */
  indicatorLabel: string;
}

/**
 * Small bell button that sits next to a metric label. On click:
 *   - Logged-out users see the auth modal.
 *   - Logged-in users see an inline popover to pick a comparison (≤/≥) and
 *     threshold. Existing alerts for the same (ticker, indicator) are listed
 *     with delete affordances so the UI stays the single source of truth.
 *
 * We deliberately do NOT support editing an alert in place — simpler model is
 * "delete + recreate" which matches how the backend enforces the
 * (ticker, indicator, comparison) unique constraint.
 */
export function AlertButton({ ticker, indicator, indicatorLabel }: AlertButtonProps) {
  const { t } = useTranslation();
  const { isAuthenticated } = useAuth();
  const { alerts, createAlert, deleteAlert } = useAlerts(ticker);
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [open, setOpen] = useState(false);
  const [comparison, setComparison] = useState<"lte" | "gte">("lte");
  const [threshold, setThreshold] = useState("");
  const [submitError, setSubmitError] = useState<string | null>(null);
  const popoverRef = useRef<HTMLDivElement>(null);

  const alertsForIndicator = alerts.filter((alert) => alert.indicator === indicator);
  const hasAlerts = alertsForIndicator.length > 0;

  // Close on click-outside / Escape.
  useEffect(() => {
    if (!open) return;
    function handleClickOutside(event: MouseEvent) {
      if (popoverRef.current && !popoverRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [open]);

  function handleToggle(event: React.MouseEvent) {
    event.preventDefault();
    event.stopPropagation();
    if (!isAuthenticated) {
      setShowAuthModal(true);
      return;
    }
    setOpen((previous) => !previous);
    setSubmitError(null);
  }

  async function handleSave() {
    if (!threshold.trim()) return;
    setSubmitError(null);
    try {
      await createAlert.mutateAsync({
        ticker,
        indicator,
        comparison,
        threshold: threshold.trim(),
      });
      setThreshold("");
    } catch {
      setSubmitError(t("alerts.save_error"));
    }
  }

  async function handleDelete(alertId: number) {
    if (!window.confirm(t("alerts.confirm_delete"))) return;
    await deleteAlert.mutateAsync(alertId);
  }

  return (
    <span className="alert-button-wrapper">
      <button
        type="button"
        className={`alert-button${hasAlerts ? " alert-button--active" : ""}`}
        aria-label={t("alerts.create")}
        title={t("alerts.create")}
        onClick={handleToggle}
      >
        <svg
          width="12"
          height="12"
          viewBox="0 0 24 24"
          fill={hasAlerts ? "currentColor" : "none"}
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
          <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
        </svg>
      </button>

      {open && (
        <div ref={popoverRef} className="alert-popover" role="dialog">
          <div className="alert-popover-title">
            {t("alerts.create")} · {indicatorLabel}
          </div>

          <div className="alert-popover-row">
            <label className="alert-popover-label">{t("alerts.comparison")}</label>
            <select
              className="alert-popover-input"
              value={comparison}
              onChange={(event) => setComparison(event.target.value as "lte" | "gte")}
            >
              <option value="lte">{t("alerts.comparison_lte")}</option>
              <option value="gte">{t("alerts.comparison_gte")}</option>
            </select>
          </div>

          <div className="alert-popover-row">
            <label className="alert-popover-label">{t("alerts.threshold")}</label>
            <input
              type="number"
              step="any"
              className="alert-popover-input"
              value={threshold}
              onChange={(event) => setThreshold(event.target.value)}
            />
          </div>

          {submitError && <div className="alert-popover-error">{submitError}</div>}

          <button
            type="button"
            className="alert-popover-save"
            onClick={handleSave}
            disabled={!threshold.trim() || createAlert.isPending}
          >
            {t("alerts.save")}
          </button>

          {hasAlerts && (
            <ul className="alert-popover-list">
              {alertsForIndicator.map((alert) => (
                <li key={alert.id} className="alert-popover-item">
                  <span className="alert-popover-item-text">
                    {alert.comparison === "lte"
                      ? t("alerts.comparison_lte")
                      : t("alerts.comparison_gte")}{" "}
                    {alert.threshold}
                    {alert.triggered_at && (
                      <span className="alert-popover-item-triggered"> · {t("alerts.active")}</span>
                    )}
                  </span>
                  <button
                    type="button"
                    className="alert-popover-item-delete"
                    onClick={() => handleDelete(alert.id)}
                    aria-label={t("alerts.delete")}
                  >
                    ×
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {showAuthModal && (
        <AuthModal
          onClose={() => setShowAuthModal(false)}
          onSuccess={() => setShowAuthModal(false)}
          message={t("alerts.must_login")}
        />
      )}
    </span>
  );
}
