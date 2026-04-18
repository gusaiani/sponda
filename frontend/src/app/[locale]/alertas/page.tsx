"use client";

import Link from "next/link";
import { useAuth } from "../../../hooks/useAuth";
import { useAlerts } from "../../../hooks/useAlerts";
import { useTranslation } from "../../../i18n";
import { logoUrl } from "../../../utils/format";
import "../../../styles/alerts-page.css";

/**
 * Human-readable labels for each alert-capable indicator. Intentionally local
 * (not shared) so this page can evolve separately from the metric card.
 */
const INDICATOR_LABELS: Record<string, string> = {
  current_price: "Price",
  market_cap: "Market Cap",
  pe10: "PE10",
  pfcf10: "PFCF10",
  peg: "PEG",
  pfcf_peg: "P/FCF PEG",
  debt_to_equity: "Debt / Equity",
  debt_ex_lease_to_equity: "Debt (ex-lease) / Eq.",
  liabilities_to_equity: "Liab / Equity",
  debt_to_avg_earnings: "Debt / Avg Earnings",
  debt_to_avg_fcf: "Debt / Avg FCF",
};

export default function AlertsPage() {
  const { t, locale } = useTranslation();
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const { alerts, isLoading: alertsLoading, deleteAlert } = useAlerts();

  if (authLoading) {
    return (
      <div className="alerts-page">
        <p className="alerts-page-text">{t("common.loading")}</p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="alerts-page">
        <h1 className="alerts-page-title">{t("alerts.page_title")}</h1>
        <p className="alerts-page-text">{t("alerts.must_login")}</p>
        <p className="auth-link">
          <Link href={`/${locale}/login`}>{t("auth.do_login")}</Link>
        </p>
      </div>
    );
  }

  function handleDelete(alertId: number) {
    if (!window.confirm(t("alerts.confirm_delete"))) return;
    deleteAlert.mutate(alertId);
  }

  return (
    <div className="alerts-page">
      <h1 className="alerts-page-title">{t("alerts.page_title")}</h1>

      {alertsLoading ? (
        <p className="alerts-page-text">{t("common.loading")}</p>
      ) : alerts.length === 0 ? (
        <p className="alerts-page-empty">{t("alerts.no_alerts")}</p>
      ) : (
        <ul className="alerts-page-list">
          {alerts.map((alert) => {
            const indicatorLabel = INDICATOR_LABELS[alert.indicator] ?? alert.indicator;
            const operator = alert.comparison === "lte" ? "≤" : "≥";
            const isTriggered = alert.triggered_at !== null;
            return (
              <li key={alert.id} className="alerts-page-item">
                <Link
                  href={`/${locale}/${alert.ticker}`}
                  className="alerts-page-item-link"
                >
                  <img
                    className="alerts-page-item-logo"
                    src={logoUrl(alert.ticker)}
                    alt=""
                    loading="lazy"
                    onError={(event) => {
                      (event.target as HTMLImageElement).style.display = "none";
                    }}
                  />
                  <span className="alerts-page-item-ticker">{alert.ticker}</span>
                  <span className="alerts-page-item-condition">
                    {indicatorLabel} {operator} {alert.threshold}
                  </span>
                  {isTriggered && (
                    <span className="alerts-page-item-badge">
                      {t("alerts.triggered_badge")}
                    </span>
                  )}
                </Link>
                <button
                  className="alerts-page-item-delete"
                  type="button"
                  aria-label={t("alerts.delete")}
                  title={t("alerts.delete")}
                  onClick={() => handleDelete(alert.id)}
                  disabled={deleteAlert.isPending}
                >
                  ×
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
