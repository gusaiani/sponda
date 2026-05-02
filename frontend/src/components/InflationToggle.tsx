import { useTranslation } from "../i18n";

const INFLATION_SERIES_BY_CURRENCY: Record<string, string> = {
  BRL: "IPCA (Brazil)",
  USD: "US CPI",
  EUR: "Eurozone HICP",
  DKK: "Denmark CPI",
  JPY: "Japan CPI",
  GBP: "UK CPI",
  CNY: "China CPI",
  CHF: "Switzerland CPI",
  CAD: "Canada CPI",
  AUD: "Australia CPI",
  MXN: "Mexico CPI",
  INR: "India CPI",
  KRW: "Korea CPI",
  NOK: "Norway CPI",
  SEK: "Sweden CPI",
  ZAR: "South Africa CPI",
  ILS: "Israel CPI",
  TRY: "Turkey CPI",
  IDR: "Indonesia CPI",
  PLN: "Poland CPI",
  CZK: "Czechia CPI",
  HUF: "Hungary CPI",
  NZD: "New Zealand CPI",
  CLP: "Chile CPI",
};

function inflationSeriesLabel(reportedCurrency: string | undefined): string {
  if (!reportedCurrency) return "no inflation series";
  return INFLATION_SERIES_BY_CURRENCY[reportedCurrency.toUpperCase()] ?? "no inflation series";
}

export type InflationMode = "nominal" | "adjusted";

interface Props {
  mode: InflationMode;
  onModeChange: (mode: InflationMode) => void;
  reportedCurrency: string | undefined;
}

export function InflationToggle({ mode, onModeChange, reportedCurrency }: Props) {
  const { t } = useTranslation();
  const adjustedTooltip = t("fundamentals.adjustedTooltip").replace(
    "{series}",
    inflationSeriesLabel(reportedCurrency),
  );

  return (
    <div className="inflation-toggle" aria-label={t("fundamentals.inflationLabel")}>
      <span className="inflation-toggle-label">{t("fundamentals.inflationLabel")}</span>
      <div className="inflation-toggle-pills">
        <button
          type="button"
          className={`inflation-toggle-pill ${mode === "nominal" ? "inflation-toggle-pill-active" : ""}`}
          onClick={() => onModeChange("nominal")}
        >
          {t("fundamentals.nominal")}
        </button>
        <button
          type="button"
          className={`inflation-toggle-pill ${mode === "adjusted" ? "inflation-toggle-pill-active" : ""}`}
          onClick={() => onModeChange("adjusted")}
          title={adjustedTooltip}
        >
          {t("fundamentals.adjusted")}
        </button>
      </div>
    </div>
  );
}
