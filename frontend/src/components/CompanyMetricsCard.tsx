import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { createPortal } from "react-dom";
import "../styles/card.css";
import "../styles/share-dropdown.css";
import { MiniChart, type DataPoint } from "./MiniChart";
import { AlertButton } from "./AlertButton";
import { useTranslation, type TranslationKey } from "../i18n";
import { isBrazilianTicker } from "../utils/ticker";
import { getSubsector } from "../utils/subsector";

/* ── Exported helpers (tested in CompanyMetricsCard.test.ts) ── */

export function buildMarketCapSeries(
  priceHistory: { date: string; adjustedClose: number }[],
  marketCap: number | null,
  currentPrice: number,
  years: number,
): DataPoint[] {
  if (!priceHistory.length || !marketCap || !currentPrice) return [];
  const sharesOutstanding = marketCap / currentPrice;
  const currentYear = new Date().getFullYear();
  const startYear = currentYear - years;
  const filtered = priceHistory.filter(
    (p) => parseInt(p.date.slice(0, 4), 10) > startYear,
  );
  if (!filtered.length) return [];
  const step = Math.max(1, Math.floor(filtered.length / 150));
  const series: DataPoint[] = [];
  for (let i = 0; i < filtered.length; i += step) {
    const point = filtered[i];
    series.push({
      label: point.date,
      value: point.adjustedClose * sharesOutstanding,
      yearTick: point.date.slice(2, 4),
    });
  }
  const last = filtered[filtered.length - 1];
  if (series[series.length - 1]?.label !== last.date) {
    series.push({
      label: last.date,
      value: last.adjustedClose * sharesOutstanding,
      yearTick: last.date.slice(2, 4),
    });
  }
  return series;
}

/**
 * Rolling N-year average of a per-year numeric map, ending at `year`.
 * Returns null when the window has no data or the average is non-positive.
 */
export function rollingAverage(
  valuesByYear: Map<number, number>,
  year: number,
  windowYears: number,
): number | null {
  const samples: number[] = [];
  for (let y = year - windowYears + 1; y <= year; y += 1) {
    const v = valuesByYear.get(y);
    if (v != null) samples.push(v);
  }
  if (!samples.length) return null;
  const average = samples.reduce((sum, value) => sum + value, 0) / samples.length;
  return average > 0 ? average : null;
}

/**
 * Build a daily ratio series of (market_cap_at_date / rolling_avg_denominator).
 * The window size equals the visible `years` (driven by the slider), so the
 * chart always reflects the same window length as the headline P/L{years}.
 * The denominator updates once per calendar year; price moves daily.
 */
export function buildRollingRatioSeries(
  priceHistory: { date: string; adjustedClose: number }[],
  marketCap: number | null,
  currentPrice: number | null,
  denominatorsByYear: Map<number, number>,
  years: number,
): DataPoint[] {
  if (!priceHistory.length || !marketCap || !currentPrice) return [];
  const sharesOutstanding = marketCap / currentPrice;
  const currentYear = new Date().getFullYear();
  const startYear = currentYear - years;
  const filtered = priceHistory.filter(
    (p) => parseInt(p.date.slice(0, 4), 10) > startYear,
  );
  if (!filtered.length) return [];
  const averageCache = new Map<number, number | null>();
  const step = Math.max(1, Math.floor(filtered.length / 150));
  const series: DataPoint[] = [];
  const appendPoint = (point: { date: string; adjustedClose: number }) => {
    const year = parseInt(point.date.slice(0, 4), 10);
    if (!averageCache.has(year)) {
      averageCache.set(year, rollingAverage(denominatorsByYear, year, years));
    }
    const average = averageCache.get(year);
    if (average == null) return;
    const marketCapAtDate = point.adjustedClose * sharesOutstanding;
    series.push({
      label: point.date,
      value: marketCapAtDate / average,
      yearTick: point.date.slice(2, 4),
    });
  };
  for (let i = 0; i < filtered.length; i += step) appendPoint(filtered[i]);
  const last = filtered[filtered.length - 1];
  if (series[series.length - 1]?.label !== last.date) appendPoint(last);
  return series;
}

export function buildDebtToRollingAvgSeries(
  fundamentals: import("../hooks/useFundamentals").FundamentalsYear[],
  denominatorField: "netIncomeAdjusted" | "fcfAdjusted",
  windowYears: number,
  sliceYears: number,
): DataPoint[] {
  if (!fundamentals.length || windowYears < 1) return [];
  const sorted = [...fundamentals].sort((a, b) => a.year - b.year);
  if (sorted.length < windowYears) return [];

  const points: DataPoint[] = [];
  for (let i = windowYears - 1; i < sorted.length; i++) {
    const current = sorted[i];
    if (current.totalDebt === null) continue;

    const window = sorted.slice(i - windowYears + 1, i + 1);
    const values = window.map((y) => y[denominatorField]);
    if (values.some((v) => v === null || v === undefined)) continue;

    const avg = (values as number[]).reduce((a, b) => a + b, 0) / window.length;
    if (avg <= 0) continue;

    points.push({
      label: String(current.year),
      value: current.totalDebt / avg,
      yearTick: String(current.year).slice(2),
    });
  }

  return points.slice(-sliceYears);
}

export function buildQuarterlyRatioSeries(
  quarterlyRatios: { date: string; debtToEquity: number | null; liabilitiesToEquity: number | null }[],
  field: "debtToEquity" | "liabilitiesToEquity",
  years: number,
): DataPoint[] {
  if (!quarterlyRatios.length) return [];
  const currentYear = new Date().getFullYear();
  const startYear = currentYear - years;
  const filtered = quarterlyRatios.filter(
    (r) => parseInt(r.date.slice(0, 4), 10) > startYear && r[field] !== null,
  );
  return filtered.map((r) => ({
    label: r.date,
    value: r[field]!,
    yearTick: r.date.slice(2, 4),
  }));
}

export function formatYearsOfData(
  pe10Years: number,
  pfcf10Years: number,
): string {
  if (pe10Years === pfcf10Years) return String(pe10Years);
  return `L: ${pe10Years} · FCL: ${pfcf10Years}`;
}

/* ── Metric IDs for sharing ── */

const METRIC_IDS = {
  debtToEquity: "gross-debt-eq",
  debtExLease: "debt-ex-lease-eq",
  liabToEquity: "liab-eq",
  debtToEarnings: "gross-debt-earnings",
  debtToFCF: "gross-debt-fcf",
  currentPrice: "current-price",
  marketCap: "market-cap",
  yearsOfData: "years-of-data",
  pe10: "pe10",
  peg: "peg",
  cagrEarnings: "cagr-earnings",
  pfcf10: "pfcf10",
  pfcfg: "pfcfg",
  cagrFCF: "cagr-fcf",
} as const;

function formatMultiple(value: number, locale: string): string {
  return `${formatNumber(value, 1, locale)}×`;
}

/**
 * Map UI metric DOM ids → backend alert indicator keys.
 * Only indicators that the IndicatorAlert model accepts are present; metrics
 * without a snapshot field (currentPrice, yearsOfData, cagr*) are intentionally
 * omitted so the AlertButton is not rendered next to them.
 */
const ALERT_INDICATOR_BY_METRIC_ID: Record<string, string> = {
  "current-price": "current_price",
  "market-cap": "market_cap",
  "pe10": "pe10",
  "pfcf10": "pfcf10",
  "peg": "peg",
  "pfcfg": "pfcf_peg",
  "gross-debt-eq": "debt_to_equity",
  "debt-ex-lease-eq": "debt_ex_lease_to_equity",
  "liab-eq": "liabilities_to_equity",
  "gross-debt-earnings": "debt_to_avg_earnings",
  "gross-debt-fcf": "debt_to_avg_fcf",
};

/** Per-metric chart value formatter — multiples show "×", ratios show 2 decimals. */
function getChartValueFormatters(locale: string): Record<string, (value: number) => string> {
  return {
    [METRIC_IDS.pe10]: (value) => formatMultiple(value, locale),
    [METRIC_IDS.pfcf10]: (value) => formatMultiple(value, locale),
    [METRIC_IDS.peg]: (value) => formatNumber(value, 2, locale),
    [METRIC_IDS.pfcfg]: (value) => formatNumber(value, 2, locale),
    [METRIC_IDS.debtToEquity]: (value) => formatNumber(value, 2, locale),
    [METRIC_IDS.debtExLease]: (value) => formatNumber(value, 2, locale),
    [METRIC_IDS.liabToEquity]: (value) => formatNumber(value, 2, locale),
    [METRIC_IDS.debtToEarnings]: (value) => formatNumber(value, 1, locale),
    [METRIC_IDS.debtToFCF]: (value) => formatNumber(value, 1, locale),
  };
}

/* ── Share button + dropdown (matches header ShareDropdown) ── */

function ShareButton({ metricId, years }: { metricId: string; years?: number }) {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const yearsParam = years && years !== 10 ? `?years=${years}` : "";
  const shareUrl = typeof window !== "undefined"
    ? `https://sponda.capital${window.location.pathname}${yearsParam}#${metricId}`
    : "";
  const shareText = t("metrics.share_indicator");
  const encodedUrl = encodeURIComponent(shareUrl);
  const encodedText = encodeURIComponent(shareText);

  useEffect(() => {
    if (!isOpen) return;
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsOpen(false);
        setCopied(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isOpen]);

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(shareUrl);
    setCopied(true);
    setTimeout(() => {
      setCopied(false);
      setIsOpen(false);
    }, 1200);
  }, [shareUrl]);

  return (
    <>
      <button
        className="share-btn"
        type="button"
        aria-label={shareText}
        onClick={(event) => {
          event.stopPropagation();
          setIsOpen(!isOpen);
          setCopied(false);
        }}
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="18" cy="5" r="3" />
          <circle cx="6" cy="12" r="3" />
          <circle cx="18" cy="19" r="3" />
          <line x1="8.59" y1="13.51" x2="15.42" y2="17.49" />
          <line x1="15.41" y1="6.51" x2="8.59" y2="10.49" />
        </svg>
      </button>
      {isOpen && (
        <div className="metric-share-menu share-dropdown-menu" ref={menuRef} onClick={(event) => event.stopPropagation()}>
          <a
            className="share-dropdown-option"
            href={`https://x.com/intent/tweet?text=${encodedText}&url=${encodedUrl}`}
            target="_blank"
            rel="noopener noreferrer"
            onClick={() => setIsOpen(false)}
          >
            <svg viewBox="0 0 24 24" fill="#000000" className="share-dropdown-icon">
              <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
            </svg>
            <span>X / Twitter</span>
          </a>
          <a
            className="share-dropdown-option"
            href={`https://wa.me/?text=${encodedText}%20${encodedUrl}`}
            target="_blank"
            rel="noopener noreferrer"
            onClick={() => setIsOpen(false)}
          >
            <svg viewBox="0 0 24 24" fill="#25D366" className="share-dropdown-icon">
              <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
            </svg>
            <span>WhatsApp</span>
          </a>
          <a
            className="share-dropdown-option"
            href={`https://t.me/share/url?url=${encodedUrl}&text=${encodedText}`}
            target="_blank"
            rel="noopener noreferrer"
            onClick={() => setIsOpen(false)}
          >
            <svg viewBox="0 0 24 24" fill="#26A5E4" className="share-dropdown-icon">
              <path d="M11.944 0A12 12 0 000 12a12 12 0 0012 12 12 12 0 0012-12A12 12 0 0012 0a12 12 0 00-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 01.171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.479.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z" />
            </svg>
            <span>Telegram</span>
          </a>
          <a
            className="share-dropdown-option"
            href={`https://www.linkedin.com/sharing/share-offsite/?url=${encodedUrl}`}
            target="_blank"
            rel="noopener noreferrer"
            onClick={() => setIsOpen(false)}
          >
            <svg viewBox="0 0 24 24" fill="#0A66C2" className="share-dropdown-icon">
              <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
            </svg>
            <span>LinkedIn</span>
          </a>
          <button
            className="share-dropdown-option"
            onClick={handleCopy}
          >
            {copied ? (
              <svg viewBox="0 0 24 24" fill="none" stroke="#16a34a" strokeWidth="2.5" className="share-dropdown-icon">
                <polyline points="20 6 9 17 4 12" />
              </svg>
            ) : (
              <svg viewBox="0 0 24 24" fill="none" stroke="#5570a0" strokeWidth="1.5" className="share-dropdown-icon">
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" />
              </svg>
            )}
            <span>{copied ? t("share.copied") : t("share.copy_link")}</span>
          </button>
        </div>
      )}
    </>
  );
}

interface QuarterlyEarningsDetail {
  end_date: string;
  net_income: number;
}

interface PE10YearlyBreakdown {
  year: number;
  nominalNetIncome: number;
  ipcaFactor: number;
  adjustedNetIncome: number;
  quarters: number;
  quarterlyDetail: QuarterlyEarningsDetail[];
}

interface QuarterlyCFDetail {
  end_date: string;
  operating_cash_flow: number;
  investment_cash_flow: number;
  fcf: number;
}

interface PFCF10YearlyBreakdown {
  year: number;
  nominalFCF: number;
  ipcaFactor: number;
  adjustedFCF: number;
  quarters: number;
  quarterlyDetail: QuarterlyCFDetail[];
}

interface QuoteData {
  ticker: string;
  name: string;
  logo: string;
  currentPrice: number;
  marketCap: number | null;
  /** ISO 4217 of the listing-currency (the price/marketCap currency). */
  listingCurrency?: string;
  /** ISO 4217 of the reporting (statement) currency. Drives the symbol used
   * for absolute values like revenue, FCF, equity. */
  reportedCurrency?: string;
  pe10: number | null;
  avgAdjustedNetIncome: number | null;
  pe10YearsOfData: number;
  pe10Label: string;
  pe10Error: string | null;
  pe10AnnualData: boolean;
  pe10CalculationDetails: PE10YearlyBreakdown[];
  pfcf10: number | null;
  avgAdjustedFCF: number | null;
  pfcf10YearsOfData: number;
  pfcf10Label: string;
  pfcf10Error: string | null;
  pfcf10AnnualData: boolean;
  pfcf10CalculationDetails: PFCF10YearlyBreakdown[];
  maxYearsAvailable: number;
  // Leverage
  debtToEquity: number | null;
  debtExLeaseToEquity: number | null;
  liabilitiesToEquity: number | null;
  leverageError: string | null;
  leverageDate: string | null;
  totalDebt: number | null;
  totalLease: number | null;
  totalLiabilities: number | null;
  stockholdersEquity: number | null;
  // Debt coverage
  debtToAvgEarnings: number | null;
  debtToAvgFCF: number | null;
  // PEG
  peg: number | null;
  earningsCAGR: number | null;
  pegError: string | null;
  earningsCAGRMethod: "endpoint" | "regression" | null;
  earningsCAGRExcludedYears: number[];
  // PFCLG
  pfcfPeg: number | null;
  fcfCAGR: number | null;
  pfcfPegError: string | null;
  fcfCAGRMethod: "endpoint" | "regression" | null;
  fcfCAGRExcludedYears: number[];
}

interface CompanyMetricsCardProps {
  data: QuoteData;
  years: number;
  maxYears: number;
  onYearsChange: (years: number) => void;
  sector?: string;
  fundamentals?: import("../hooks/useFundamentals").FundamentalsYear[];
  quarterlyRatios?: import("../hooks/useFundamentals").QuarterlyBalanceRatio[];
  priceHistory?: { date: string; adjustedClose: number }[];
}

const FINANCIAL_SUBSECTORS = new Set(["Bancos", "Seguros", "Infraestrutura de Mercado"]);

function isFinancialInstitution(name: string, sector: string): boolean {
  if (sector !== "Finance") return false;
  const subsector = getSubsector(name, sector);
  return FINANCIAL_SUBSECTORS.has(subsector);
}

type ModalKey =
  | "debtToEquity" | "debtExLease" | "liabToEquity"
  | "debtToEarnings" | "debtToFCF"
  | "marketCap"
  | "pl10" | "peg" | "cagrEarnings"
  | "pfcl10" | "pfclg" | "cagrFCF"
  | null;

import { localizeLabel, formatNumber, formatLargeNumber, currencySymbol, formatQuarterLabel } from "../utils/format";

/* ── Error code → i18n key mapping ── */

const ERROR_KEYS: Record<string, TranslationKey> = {
  no_earnings_data: "metrics.error.no_earnings_data",
  no_cashflow_data: "metrics.error.no_cashflow_data",
  pe_unavailable: "metrics.error.pe_unavailable",
  pe_negative: "metrics.error.pe_negative",
  pfcf_unavailable: "metrics.error.pfcf_unavailable",
  pfcf_negative: "metrics.error.pfcf_negative",
  negative_growth: "metrics.error.negative_growth",
};

function translateError(error: string | null, t: (key: TranslationKey) => string): string | null {
  if (!error) return null;
  const key = ERROR_KEYS[error];
  return key ? t(key) : error;
}

/* ── Inline ? button ── */

function InfoBtn({ onClick, ariaLabel }: { onClick: () => void; ariaLabel: string }) {
  return (
    <button className="info-btn" onClick={onClick} type="button" aria-label={ariaLabel}>
      ?
    </button>
  );
}

/* ── Modal ── */

function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", handleKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", handleKey);
      document.body.style.overflow = "";
    };
  }, [onClose]);

  return createPortal(
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2 className="modal-title">{title}</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        <div className="modal-body">
          {children}
        </div>
      </div>
    </div>,
    document.body,
  );
}

/** formatLargeNumber bound to a specific ticker's currency and locale.
 * When `reportedCurrency` is provided (foreign-listed companies that file in
 * a different currency than they trade in), the displayed values use that
 * currency's symbol — keeps the Fundamentos tab honest about what currency
 * the underlying numbers are in. */
function makeFormatAmount(ticker: string, locale: string, reportedCurrency?: string) {
  return (value: number) => formatLargeNumber(value, ticker, locale, reportedCurrency);
}

/* ── Balance sheet components helper ── */

function BalanceSheetComponents({ data }: { data: QuoteData }) {
  const { t, locale } = useTranslation();
  const formatAmount = makeFormatAmount(data.ticker, locale, data.reportedCurrency);
  if (data.stockholdersEquity === null) return null;
  return (
    <div className="pe10-calc-details">
      {data.leverageDate && (
        <div className="pe10-calc-section">
          <div className="pe10-calc-section-title">{t("modal.balance_date")}</div>
          <div className="pe10-calc-formula">
            <span>{t("modal.reference")}</span>
            <span className="pe10-calc-formula-val">{data.leverageDate}</span>
          </div>
        </div>
      )}
      <div className="pe10-calc-section">
        <div className="pe10-calc-section-title">{t("modal.components")}</div>
        {data.totalDebt !== null && (
          <div className="pe10-calc-formula">
            <span>{t("modal.gross_debt")}</span>
            <span className="pe10-calc-formula-val">{formatAmount(data.totalDebt)}</span>
          </div>
        )}
        {data.totalLease !== null && (
          <div className="pe10-calc-formula">
            <span>{t("modal.leases")}</span>
            <span className="pe10-calc-formula-val">{formatAmount(data.totalLease)}</span>
          </div>
        )}
        {data.totalLiabilities !== null && (
          <div className="pe10-calc-formula">
            <span>{t("modal.total_liabilities")}</span>
            <span className="pe10-calc-formula-val">{formatAmount(data.totalLiabilities)}</span>
          </div>
        )}
        <div className="pe10-calc-formula">
          <span>{t("modal.equity")}</span>
          <span className="pe10-calc-formula-val">{formatAmount(data.stockholdersEquity)}</span>
        </div>
      </div>
    </div>
  );
}

/* ── Per-metric modal content ── */

function DebtToEquityInfo({ data }: { data: QuoteData }) {
  const { t, locale } = useTranslation();
  const formatAmount = makeFormatAmount(data.ticker, locale, data.reportedCurrency);
  return (
    <>
      <div className="modal-explainer">
        <p>{t("modal.debt_equity_explain")}</p>
        <p>{t("modal.debt_equity_compare")}</p>
        <div className="modal-video">
          <iframe
            src="https://www.youtube.com/embed/cpMHtPlIQIQ"
            title="Gross Debt / Equity"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen
          />
        </div>
      </div>
      <BalanceSheetComponents data={data} />
      {data.debtToEquity !== null && data.stockholdersEquity !== null && (
        <div className="pe10-calc-details">
          <div className="pe10-calc-section">
            <div className="pe10-calc-section-title">{t("modal.calculation")}</div>
            <div className="pe10-calc-formula">
              <span>{formatAmount(data.totalDebt!)} ÷ {formatAmount(data.stockholdersEquity)}</span>
              <span className="pe10-calc-formula-val">= {formatNumber(data.debtToEquity, 2, locale)}</span>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function DebtExLeaseInfo({ data }: { data: QuoteData }) {
  const { t, locale } = useTranslation();
  const formatAmount = makeFormatAmount(data.ticker, locale, data.reportedCurrency);
  return (
    <>
      <div className="modal-explainer">
        <p>{t("modal.debt_ex_lease_explain")}</p>
      </div>
      <BalanceSheetComponents data={data} />
      {data.debtExLeaseToEquity !== null && data.totalDebt !== null && data.stockholdersEquity !== null && (
        <div className="pe10-calc-details">
          <div className="pe10-calc-section">
            <div className="pe10-calc-section-title">{t("modal.calculation")}</div>
            <div className="pe10-calc-formula">
              <span>({formatAmount(data.totalDebt)} − {formatAmount(data.totalLease ?? 0)}) ÷ {formatAmount(data.stockholdersEquity)}</span>
              <span className="pe10-calc-formula-val">= {formatNumber(data.debtExLeaseToEquity, 2, locale)}</span>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function LiabToEquityInfo({ data }: { data: QuoteData }) {
  const { t, locale } = useTranslation();
  const formatAmount = makeFormatAmount(data.ticker, locale, data.reportedCurrency);
  return (
    <>
      <div className="modal-explainer">
        <p>{t("modal.liab_equity_explain")}</p>
        <p>{t("modal.liab_equity_broader")}</p>
        <div className="modal-video">
          <iframe
            src="https://www.youtube.com/embed/g4NIUZs0Qf8"
            title="Liabilities / Equity"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen
          />
        </div>
      </div>
      <BalanceSheetComponents data={data} />
      {data.liabilitiesToEquity !== null && data.stockholdersEquity !== null && (
        <div className="pe10-calc-details">
          <div className="pe10-calc-section">
            <div className="pe10-calc-section-title">{t("modal.calculation")}</div>
            <div className="pe10-calc-formula">
              <span>{formatAmount(data.totalLiabilities!)} ÷ {formatAmount(data.stockholdersEquity)}</span>
              <span className="pe10-calc-formula-val">= {formatNumber(data.liabilitiesToEquity, 2, locale)}</span>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function DebtToEarningsInfo({ data }: { data: QuoteData }) {
  const { t, locale } = useTranslation();
  const formatAmount = makeFormatAmount(data.ticker, locale, data.reportedCurrency);
  return (
    <>
      <div className="modal-explainer">
        <p>{t("modal.debt_earnings_explain")}</p>
        <p>{t("modal.debt_earnings_note")}</p>
        <div className="modal-video">
          <iframe
            src="https://www.youtube.com/embed/iEVxqV-pBjU"
            title="Debt / Earnings"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen
          />
        </div>
      </div>
      {data.totalDebt !== null && data.debtToAvgEarnings !== null && data.avgAdjustedNetIncome !== null && (
        <div className="pe10-calc-details">
          <div className="pe10-calc-section">
            <div className="pe10-calc-section-title">{t("modal.calculation")}</div>
            <div className="pe10-calc-formula">
              <span>{t("modal.gross_debt")}</span>
              <span className="pe10-calc-formula-val">{formatAmount(data.totalDebt)}</span>
            </div>
            <div className="pe10-calc-formula">
              <span>{t("modal.pl10_avg_label", { years: data.pe10YearsOfData })}</span>
              <span className="pe10-calc-formula-val">{formatAmount(data.avgAdjustedNetIncome)}</span>
            </div>
            <div className="pe10-calc-formula pe10-calc-result">
              <span>{formatAmount(data.totalDebt)} ÷ {formatAmount(data.avgAdjustedNetIncome)}</span>
              <span className="pe10-calc-formula-val">= {formatNumber(data.debtToAvgEarnings, 2, locale)}</span>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function DebtToFCFInfo({ data }: { data: QuoteData }) {
  const { t, locale } = useTranslation();
  const formatAmount = makeFormatAmount(data.ticker, locale, data.reportedCurrency);
  return (
    <>
      <div className="modal-explainer">
        <p>{t("modal.debt_fcf_explain")}</p>
        <div className="modal-video">
          <iframe
            src="https://www.youtube.com/embed/i5kq79jnk1U"
            title="Debt / Free Cash Flow"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen
          />
        </div>
      </div>
      {data.totalDebt !== null && data.debtToAvgFCF !== null && data.avgAdjustedFCF !== null && (
        <div className="pe10-calc-details">
          <div className="pe10-calc-section">
            <div className="pe10-calc-section-title">{t("modal.calculation")}</div>
            <div className="pe10-calc-formula">
              <span>{t("modal.gross_debt")}</span>
              <span className="pe10-calc-formula-val">{formatAmount(data.totalDebt)}</span>
            </div>
            <div className="pe10-calc-formula">
              <span>{t("modal.pfcl10_avg_label", { years: data.pfcf10YearsOfData })}</span>
              <span className="pe10-calc-formula-val">{formatAmount(data.avgAdjustedFCF)}</span>
            </div>
            <div className="pe10-calc-formula pe10-calc-result">
              <span>{formatAmount(data.totalDebt)} ÷ {formatAmount(data.avgAdjustedFCF)}</span>
              <span className="pe10-calc-formula-val">= {formatNumber(data.debtToAvgFCF, 2, locale)}</span>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function MarketCapInfo({ data }: { data: QuoteData }) {
  const { t, locale } = useTranslation();
  const formatAmount = makeFormatAmount(data.ticker, locale, data.reportedCurrency);
  return (
    <>
      <div className="modal-explainer">
        <p>{t("modal.market_cap_explain")}</p>
        <div className="modal-video">
          <iframe
            src="https://www.youtube.com/embed/r-nH3W5lAwE"
            title="Market Cap"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen
          />
        </div>
      </div>
      {data.marketCap !== null && data.currentPrice !== null && data.currentPrice > 0 && (
        <div className="pe10-calc-details">
          <div className="pe10-calc-section">
            <div className="pe10-calc-section-title">{t("modal.calculation")}</div>
            <div className="pe10-calc-formula">
              <span>{t("modal.market_cap_price")} × {t("modal.market_cap_shares")}</span>
              <span className="pe10-calc-formula-val">= {formatAmount(data.marketCap)}</span>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function PL10Info({ data }: { data: QuoteData }) {
  const { t, locale } = useTranslation();
  const [expandedYear, setExpandedYear] = useState<number | null>(null);
  const formatAmount = makeFormatAmount(data.ticker, locale, data.reportedCurrency);
  const label = localizeLabel(data.pe10Label, locale);
  const hasCalc = data.pe10CalculationDetails.length > 0;
  const total = hasCalc
    ? data.pe10CalculationDetails.reduce((s, y) => s + y.adjustedNetIncome, 0)
    : 0;

  return (
    <>
      <div className="modal-explainer">
        <p>{t("modal.pl10_explain", { label })}</p>
        <p>{t("modal.pl10_high_low")}</p>
      </div>

      {hasCalc && (
        <div className="pe10-calc-details">
          <h4 className="pe10-calc-title">{t("modal.how_calculated")}</h4>

          <div className="pe10-calc-section">
            <div className="pe10-calc-section-title">{t("modal.pl10_step1")}</div>
            <table className="pe10-calc-table">
              <thead>
                <tr>
                  <th>{t("modal.pl10_col_year")}</th>
                  <th>{t("modal.pl10_col_net_income")}</th>
                  <th>{isBrazilianTicker(data.ticker) ? t("modal.pl10_col_ipca_factor") : t("modal.pl10_col_cpi_factor")}</th>
                  <th>{t("modal.pl10_col_adjusted")}</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {data.pe10CalculationDetails.map((year) => (
                  <>
                    <tr key={year.year} className="pe10-calc-year-row">
                      <td>{year.year}</td>
                      <td>{formatAmount(year.nominalNetIncome)}</td>
                      <td>{formatNumber(year.ipcaFactor, 4, locale)}×</td>
                      <td>{formatAmount(year.adjustedNetIncome)}</td>
                      <td>
                        <button
                          className="pe10-calc-expand-btn"
                          onClick={() => setExpandedYear(expandedYear === year.year ? null : year.year)}
                        >
                          <span className={`pe10-explainer-chevron ${expandedYear === year.year ? "pe10-explainer-chevron-open" : ""}`}>▼</span>
                        </button>
                      </td>
                    </tr>
                    {expandedYear === year.year && year.quarterlyDetail.map((q) => (
                      <tr key={q.end_date} className="pe10-calc-quarter-row">
                        <td className="pe10-calc-quarter-label">{formatQuarterLabel(q.end_date)}</td>
                        <td colSpan={4}>{t("modal.quarterly_net_income", { value: formatAmount(q.net_income) })}</td>
                      </tr>
                    ))}
                  </>
                ))}
              </tbody>
            </table>
          </div>

          <div className="pe10-calc-section">
            <div className="pe10-calc-section-title">{t("modal.pl10_step2")}</div>
            <div className="pe10-calc-formula">
              <span>{t("modal.pl10_sum")}</span>
              <span className="pe10-calc-formula-val">{formatAmount(total)}</span>
            </div>
            <div className="pe10-calc-formula">
              <span>÷ {data.pe10YearsOfData} {t("common.year_plural")}</span>
              <span className="pe10-calc-formula-val">
                = {data.avgAdjustedNetIncome !== null ? formatAmount(data.avgAdjustedNetIncome) : "N/A"}
              </span>
            </div>
          </div>

          {data.pe10 !== null && data.avgAdjustedNetIncome !== null && data.marketCap !== null && (
            <div className="pe10-calc-section">
              <div className="pe10-calc-section-title">{t("modal.pl10_step3", { label })}</div>
              <div className="pe10-calc-formula">
                <span>{t("modal.pl10_market_cap")}</span>
                <span className="pe10-calc-formula-val">{formatAmount(data.marketCap)}</span>
              </div>
              <div className="pe10-calc-formula">
                <span>÷ {t("modal.pl10_divided_by")}</span>
                <span className="pe10-calc-formula-val">{formatAmount(data.avgAdjustedNetIncome)}</span>
              </div>
              <div className="pe10-calc-formula pe10-calc-result">
                <span>= {label}</span>
                <span className="pe10-calc-formula-val">{formatNumber(data.pe10, 2, locale)}</span>
              </div>
            </div>
          )}
        </div>
      )}
    </>
  );
}

function PFCL10Info({ data }: { data: QuoteData }) {
  const { t, locale } = useTranslation();
  const [expandedYear, setExpandedYear] = useState<number | null>(null);
  const formatAmount = makeFormatAmount(data.ticker, locale, data.reportedCurrency);
  const label = localizeLabel(data.pfcf10Label, locale);
  const hasCalc = data.pfcf10CalculationDetails.length > 0;
  const total = hasCalc
    ? data.pfcf10CalculationDetails.reduce((s, y) => s + y.adjustedFCF, 0)
    : 0;

  return (
    <>
      <div className="modal-explainer">
        <p>{t("modal.pfcl10_explain", { label })}</p>
        <p>{t("modal.pfcl10_compare", { pfclLabel: label, peLabel: localizeLabel(data.pe10Label, locale) })}</p>
      </div>

      {hasCalc && (
        <div className="pe10-calc-details">
          <h4 className="pe10-calc-title">{t("modal.how_calculated")}</h4>

          <div className="pe10-calc-section">
            <div className="pe10-calc-section-title">{t("modal.pfcl10_step1")}</div>
            <table className="pe10-calc-table">
              <thead>
                <tr>
                  <th>{t("modal.pl10_col_year")}</th>
                  <th>{t("modal.pfcl10_col_fcf")}</th>
                  <th>{isBrazilianTicker(data.ticker) ? t("modal.pl10_col_ipca_factor") : t("modal.pl10_col_cpi_factor")}</th>
                  <th>{t("modal.pfcl10_col_adjusted")}</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {data.pfcf10CalculationDetails.map((year) => (
                  <>
                    <tr key={year.year} className="pe10-calc-year-row">
                      <td>{year.year}</td>
                      <td>{formatAmount(year.nominalFCF)}</td>
                      <td>{formatNumber(year.ipcaFactor, 4, locale)}×</td>
                      <td>{formatAmount(year.adjustedFCF)}</td>
                      <td>
                        <button
                          className="pe10-calc-expand-btn"
                          onClick={() => setExpandedYear(expandedYear === year.year ? null : year.year)}
                        >
                          <span className={`pe10-explainer-chevron ${expandedYear === year.year ? "pe10-explainer-chevron-open" : ""}`}>▼</span>
                        </button>
                      </td>
                    </tr>
                    {expandedYear === year.year && year.quarterlyDetail.map((q) => (
                      <tr key={q.end_date} className="pe10-calc-quarter-row">
                        <td className="pe10-calc-quarter-label">{formatQuarterLabel(q.end_date)}</td>
                        <td colSpan={4}>
                          {t("modal.quarterly_operating", { value: formatAmount(q.operating_cash_flow) })}
                          {" · "}
                          {t("modal.quarterly_investing", { value: formatAmount(q.investment_cash_flow) })}
                        </td>
                      </tr>
                    ))}
                  </>
                ))}
              </tbody>
            </table>
          </div>

          <div className="pe10-calc-section">
            <div className="pe10-calc-section-title">{t("modal.pfcl10_step2")}</div>
            <div className="pe10-calc-formula">
              <span>{t("modal.pfcl10_sum")}</span>
              <span className="pe10-calc-formula-val">{formatAmount(total)}</span>
            </div>
            <div className="pe10-calc-formula">
              <span>÷ {data.pfcf10YearsOfData} {t("common.year_plural")}</span>
              <span className="pe10-calc-formula-val">
                = {data.avgAdjustedFCF !== null ? formatAmount(data.avgAdjustedFCF) : "N/A"}
              </span>
            </div>
          </div>

          {data.pfcf10 !== null && data.avgAdjustedFCF !== null && data.marketCap !== null && (
            <div className="pe10-calc-section">
              <div className="pe10-calc-section-title">{t("modal.pl10_step3", { label })}</div>
              <div className="pe10-calc-formula">
                <span>{t("modal.pl10_market_cap")}</span>
                <span className="pe10-calc-formula-val">{formatAmount(data.marketCap)}</span>
              </div>
              <div className="pe10-calc-formula">
                <span>÷ {t("modal.pfcl10_divided_by")}</span>
                <span className="pe10-calc-formula-val">{formatAmount(data.avgAdjustedFCF)}</span>
              </div>
              <div className="pe10-calc-formula pe10-calc-result">
                <span>= {label}</span>
                <span className="pe10-calc-formula-val">{formatNumber(data.pfcf10, 2, locale)}</span>
              </div>
            </div>
          )}
        </div>
      )}
    </>
  );
}

function PEGInfo({ data, variant }: { data: QuoteData; variant: "earnings" | "fcf" }) {
  const { t, locale } = useTranslation();
  const isEarnings = variant === "earnings";
  const label = isEarnings ? "PEG" : t("metrics.pfcfg_label");
  const baseLabel = isEarnings ? localizeLabel(data.pe10Label, locale) : localizeLabel(data.pfcf10Label, locale);
  const baseValue = isEarnings ? data.pe10 : data.pfcf10;
  const cagr = isEarnings ? data.earningsCAGR : data.fcfCAGR;
  const peg = isEarnings ? data.peg : data.pfcfPeg;
  const method = isEarnings ? data.earningsCAGRMethod : data.fcfCAGRMethod;
  const excludedYears = isEarnings ? data.earningsCAGRExcludedYears : data.fcfCAGRExcludedYears;
  const metricName = isEarnings
    ? (locale === "pt" ? "lucros" : "earnings")
    : (locale === "pt" ? "fluxo de caixa livre" : "free cash flow");
  const cagrType = isEarnings ? t("modal.cagr_real_earnings") : t("modal.cagr_real_fcf");

  return (
    <>
      <div className="modal-explainer">
        <p>{t("modal.peg_explain", { label, metricName, baseLabel, cagrType })}</p>
        <p>{t("modal.peg_below_one", { baseLabel })}</p>
        {!isEarnings && (
          <p>{t("modal.pfclg_complement")}</p>
        )}
      </div>

      {peg !== null && baseValue !== null && cagr !== null && (
        <div className="pe10-calc-details">
          <div className="pe10-calc-section">
            <div className="pe10-calc-section-title">{t("modal.calculation")}</div>
            <div className="pe10-calc-formula">
              <span>{baseLabel}</span>
              <span className="pe10-calc-formula-val">{formatNumber(baseValue, 2, locale)}</span>
            </div>
            <div className="pe10-calc-formula">
              <span>CAGR {isEarnings ? t("modal.cagr_real_earnings") : t("modal.cagr_real_fcf")}{method === "regression" ? ` (${locale === "pt" ? "regressão" : "regression"})` : ""}</span>
              <span className="pe10-calc-formula-val">{formatNumber(cagr, 2, locale)}%</span>
            </div>
            <div className="pe10-calc-formula pe10-calc-result">
              <span>{formatNumber(baseValue, 2, locale)} ÷ {formatNumber(cagr, 2, locale)}</span>
              <span className="pe10-calc-formula-val">= {formatNumber(peg, 2, locale)}</span>
            </div>
          </div>
          {method === "regression" && excludedYears.length > 0 && (
            <div className="pe10-calc-section">
              <div className="pe10-calc-section-title">{t("modal.note")}</div>
              <p className="modal-note">
                {t("modal.peg_excluded_note", { metric: isEarnings ? (locale === "pt" ? "lucro" : "earnings") : "FCL", years: excludedYears.join(", ") })}
              </p>
            </div>
          )}
        </div>
      )}
    </>
  );
}

function CAGRInfo({ data, variant }: { data: QuoteData; variant: "earnings" | "fcf" }) {
  const { t, locale } = useTranslation();
  const isEarnings = variant === "earnings";
  const method = isEarnings ? data.earningsCAGRMethod : data.fcfCAGRMethod;
  const excludedYears = isEarnings ? data.earningsCAGRExcludedYears : data.fcfCAGRExcludedYears;
  const cagr = isEarnings ? data.earningsCAGR : data.fcfCAGR;
  const metricType = isEarnings
    ? (locale === "pt" ? "dos lucros líquidos" : "of net earnings")
    : (locale === "pt" ? "do fluxo de caixa livre" : "of free cash flow");
  const metric = isEarnings ? (locale === "pt" ? "lucro" : "earnings") : "FCL";
  const metricPlural = isEarnings ? (locale === "pt" ? "os lucros" : "earnings") : (locale === "pt" ? "o FCL" : "FCF");

  return (
    <>
      <div className="modal-explainer">
        <p>{t("modal.cagr_explain", { metricType })}</p>
        {method === "endpoint" && (
          <p>{t("modal.cagr_endpoint", { metric, metricPlural })}</p>
        )}
        {method === "regression" && (
          <p>{t("modal.cagr_regression", { metric, years: excludedYears.join(", ") })}</p>
        )}
        {method === null && (
          <p>{t("modal.cagr_default", { metric })}</p>
        )}
      </div>
      {cagr !== null && (
        <div className="pe10-calc-details">
          <div className="pe10-calc-section">
            <div className="pe10-calc-section-title">{t("modal.cagr_result")}</div>
            <div className="pe10-calc-formula">
              <span>CAGR {isEarnings ? t("modal.cagr_real_earnings") : t("modal.cagr_real_fcf")}{method === "regression" ? ` (${locale === "pt" ? "regressão" : "regression"})` : ""}</span>
              <span className="pe10-calc-formula-val">{formatNumber(cagr, 2, locale)}%</span>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

/* ── Modal content router ── */

function ModalContent({ modalKey, data }: { modalKey: ModalKey; data: QuoteData }) {
  switch (modalKey) {
    case "debtToEquity": return <DebtToEquityInfo data={data} />;
    case "debtExLease": return <DebtExLeaseInfo data={data} />;
    case "liabToEquity": return <LiabToEquityInfo data={data} />;
    case "debtToEarnings": return <DebtToEarningsInfo data={data} />;
    case "debtToFCF": return <DebtToFCFInfo data={data} />;
    case "marketCap": return <MarketCapInfo data={data} />;
    case "pl10": return <PL10Info data={data} />;
    case "peg": return <PEGInfo data={data} variant="earnings" />;
    case "cagrEarnings": return <CAGRInfo data={data} variant="earnings" />;
    case "pfcl10": return <PFCL10Info data={data} />;
    case "pfclg": return <PEGInfo data={data} variant="fcf" />;
    case "cagrFCF": return <CAGRInfo data={data} variant="fcf" />;
    default: return null;
  }
}

type TFn = (key: TranslationKey, params?: Record<string, string | number>) => string;
const MODAL_TITLES: Record<string, (data: QuoteData, t: TFn, locale: string) => string> = {
  debtToEquity: (_d, t) => t("modal.title.debt_equity"),
  debtExLease: (_d, t) => t("modal.title.debt_ex_lease"),
  liabToEquity: (_d, t) => t("modal.title.liab_equity"),
  debtToEarnings: (_d, t) => t("modal.title.debt_earnings"),
  debtToFCF: (_d, t) => t("modal.title.debt_fcf"),
  marketCap: (_d, t) => t("modal.title.market_cap"),
  pl10: (d, _t, locale) => localizeLabel(d.pe10Label, locale),
  peg: (_d, t) => t("modal.title.peg"),
  cagrEarnings: (_d, t) => t("modal.title.cagr_earnings"),
  pfcl10: (d, _t, locale) => localizeLabel(d.pfcf10Label, locale),
  pfclg: (_d, t) => t("modal.title.pfclg"),
  cagrFCF: (_d, t) => t("modal.title.cagr_fcf"),
};

/* ── Main Card ── */

export function CompanyMetricsCard({ data, years, maxYears, onYearsChange, sector, fundamentals, quarterlyRatios, priceHistory }: CompanyMetricsCardProps) {
  const { t, pluralize, locale } = useTranslation();
  const [activeModal, setActiveModal] = useState<ModalKey>(null);
  const [highlightedMetric, setHighlightedMetric] = useState<string | null>(null);
  const showGraphs = true;
  const formatAmount = makeFormatAmount(data.ticker, locale, data.reportedCurrency);
  const chartValueFormatters = getChartValueFormatters(locale);

  const pl10Label = localizeLabel(data.pe10Label, locale);
  const pfcl10Label = localizeLabel(data.pfcf10Label, locale);
  const open = (key: ModalKey) => setActiveModal(key);
  const isFinancial = sector ? isFinancialInstitution(data.name, sector) : false;
  const moreInfo = t("metrics.more_info");


  /* Build chart data arrays from calculation details & fundamentals */
  const chartData = useMemo(() => {
    // Annual adjusted earnings/FCF indexed by year (IPCA-adjusted aggregates)
    const earningsByYear = new Map<number, number>();
    for (const entry of data.pe10CalculationDetails) {
      earningsByYear.set(entry.year, entry.adjustedNetIncome);
    }
    const fcfByYear = new Map<number, number>();
    for (const entry of data.pfcf10CalculationDetails) {
      fcfByYear.set(entry.year, entry.adjustedFCF);
    }

    // Daily P/L10 = price × shares / rolling-10y-avg(adjusted net income)
    const pe10Series = buildRollingRatioSeries(
      priceHistory ?? [],
      data.marketCap,
      data.currentPrice,
      earningsByYear,
      years,
    );
    // Daily P/FCL10 = price × shares / rolling-10y-avg(adjusted FCF)
    const pfcf10Series = buildRollingRatioSeries(
      priceHistory ?? [],
      data.marketCap,
      data.currentPrice,
      fcfByYear,
      years,
    );

    // PEG and P/FCL/G trend like P/L10 and P/FCL10 scaled by 1/CAGR.
    // The current CAGR is the best estimate we have for historical growth context.
    const pegSeries: DataPoint[] = data.earningsCAGR && data.earningsCAGR > 0
      ? pe10Series.map((p) => ({ ...p, value: p.value / data.earningsCAGR! }))
      : [];
    const pfcfgSeries: DataPoint[] = data.fcfCAGR && data.fcfCAGR > 0
      ? pfcf10Series.map((p) => ({ ...p, value: p.value / data.fcfCAGR! }))
      : [];

    // Quarterly earnings series (used for CAGR earnings context chart)
    const earningsSeries: DataPoint[] = [...data.pe10CalculationDetails]
      .reverse()
      .flatMap((y) =>
        y.quarterlyDetail.length > 0
          ? y.quarterlyDetail
              .sort((a, b) => a.end_date.localeCompare(b.end_date))
              .map((q) => ({
                label: q.end_date.slice(0, 7),
                value: q.net_income,
                yearTick: String(y.year).slice(2),
              }))
          : [{ label: String(y.year), value: y.adjustedNetIncome }]
      );

    // Quarterly FCF series (used for CAGR FCF context chart)
    const fcfSeries: DataPoint[] = [...data.pfcf10CalculationDetails]
      .reverse()
      .flatMap((y) =>
        y.quarterlyDetail.length > 0
          ? y.quarterlyDetail
              .sort((a, b) => a.end_date.localeCompare(b.end_date))
              .map((q) => ({
                label: q.end_date.slice(0, 7),
                value: q.fcf,
                yearTick: String(y.year).slice(2),
              }))
          : [{ label: String(y.year), value: y.adjustedFCF }]
      );

    const sortedFundamentals = (fundamentals ?? [])
      .sort((a, b) => a.year - b.year)
      .slice(-years);

    const debtEquitySeries: DataPoint[] = buildQuarterlyRatioSeries(
      quarterlyRatios ?? [],
      "debtToEquity",
      years,
    );

    const liabEquitySeries: DataPoint[] = buildQuarterlyRatioSeries(
      quarterlyRatios ?? [],
      "liabilitiesToEquity",
      years,
    );

    // Rolling N-year debt-coverage ratios — matches the main number's formula
    // at each historical year. N = slider window (same as PE10 / PFCF10 window).
    const debtToEarningsSeries: DataPoint[] = buildDebtToRollingAvgSeries(
      fundamentals ?? [],
      "netIncomeAdjusted",
      data.pe10YearsOfData || years,
      years,
    );

    const debtToFCFSeries: DataPoint[] = buildDebtToRollingAvgSeries(
      fundamentals ?? [],
      "fcfAdjusted",
      data.pfcf10YearsOfData || years,
      years,
    );

    const marketCapSeries: DataPoint[] = buildMarketCapSeries(
      priceHistory ?? [],
      data.marketCap,
      data.currentPrice,
      years,
    );

    // Weekly prices from daily price history
    const priceSeries: DataPoint[] = [];
    if (priceHistory?.length) {
      const currentYear = new Date().getFullYear();
      const startYear = currentYear - years;
      const filtered = priceHistory.filter(
        (p) => parseInt(p.date.slice(0, 4), 10) > startYear
      );
      // Sample to weekly (~1 per 5 trading days)
      const step = Math.max(1, Math.floor(filtered.length / 150));
      for (let i = 0; i < filtered.length; i += step) {
        const point = filtered[i];
        const yearStr = point.date.slice(2, 4);
        priceSeries.push({
          label: point.date,
          value: point.adjustedClose,
          yearTick: yearStr,
        });
      }
      // Always include the last point
      if (filtered.length > 0) {
        const last = filtered[filtered.length - 1];
        if (priceSeries[priceSeries.length - 1]?.label !== last.date) {
          priceSeries.push({
            label: last.date,
            value: last.adjustedClose,
            yearTick: last.date.slice(2, 4),
          });
        }
      }
    }

    return {
      [METRIC_IDS.currentPrice]: priceSeries,
      [METRIC_IDS.marketCap]: marketCapSeries,
      [METRIC_IDS.pe10]: pe10Series,
      [METRIC_IDS.peg]: pegSeries,
      [METRIC_IDS.cagrEarnings]: earningsSeries,
      [METRIC_IDS.pfcf10]: pfcf10Series,
      [METRIC_IDS.pfcfg]: pfcfgSeries,
      [METRIC_IDS.cagrFCF]: fcfSeries,
      [METRIC_IDS.debtToEquity]: debtEquitySeries,
      [METRIC_IDS.debtExLease]: debtEquitySeries,
      [METRIC_IDS.liabToEquity]: liabEquitySeries,
      [METRIC_IDS.debtToEarnings]: debtToEarningsSeries,
      [METRIC_IDS.debtToFCF]: debtToFCFSeries,
    } as Record<string, DataPoint[]>;
  }, [data.pe10CalculationDetails, data.pfcf10CalculationDetails, data.pe10YearsOfData, data.pfcf10YearsOfData, data.marketCap, data.currentPrice, data.earningsCAGR, data.fcfCAGR, fundamentals, quarterlyRatios, priceHistory, years]);

  /* Highlight metric from URL hash */
  useEffect(() => {
    const hash = window.location.hash.slice(1);
    if (!hash) return;
    const allMetricIds = Object.values(METRIC_IDS) as string[];
    if (!allMetricIds.includes(hash)) return;
    setHighlightedMetric(hash);
    const element = document.getElementById(hash);
    if (element) {
      setTimeout(() => element.scrollIntoView({ behavior: "smooth", block: "center" }), 300);
    }
  }, []);

  const metricBlockProps = (metricId: string) => ({
    className: `metric-block${showGraphs && chartData[metricId]?.length >= 2 ? " metric-block--graph" : ""}${highlightedMetric === metricId ? " metric-block-highlighted" : ""}`,
    onMouseLeave: highlightedMetric === metricId ? () => setHighlightedMetric(null) : undefined,
  });

  const renderChart = (metricId: string) => {
    if (!showGraphs) return null;
    const series = chartData[metricId];
    if (!series || series.length < 2) return null;
    const formatter = chartValueFormatters[metricId];
    return <MiniChart data={series} formatValue={formatter} />;
  };

  const currentValueByIndicator: Record<string, number | null> = {
    current_price: data.currentPrice,
    market_cap: data.marketCap,
    pe10: data.pe10,
    pfcf10: data.pfcf10,
    peg: data.peg,
    pfcf_peg: data.pfcfPeg,
    debt_to_equity: data.debtToEquity,
    debt_ex_lease_to_equity: data.debtExLeaseToEquity,
    liabilities_to_equity: data.liabilitiesToEquity,
    debt_to_avg_earnings: data.debtToAvgEarnings,
    debt_to_avg_fcf: data.debtToAvgFCF,
  };

  const renderAlertButton = (metricId: string, indicatorLabel: string) => {
    const indicatorKey = ALERT_INDICATOR_BY_METRIC_ID[metricId];
    if (!indicatorKey) return null;
    return (
      <div className="metric-block-alert-btn">
        <AlertButton
          ticker={data.ticker}
          indicator={indicatorKey}
          indicatorLabel={indicatorLabel}
          currentValue={currentValueByIndicator[indicatorKey] ?? null}
        />
      </div>
    );
  };

  return (
    <article className="pe10-card" aria-label={`${data.name} (${data.ticker})`}>
      {/* ── Key stats ── */}
      <div className="metrics-row">
        <div id={METRIC_IDS.currentPrice} {...metricBlockProps(METRIC_IDS.currentPrice)}>
          {renderAlertButton(METRIC_IDS.currentPrice, t("metrics.current_price"))}
          <ShareButton metricId={METRIC_IDS.currentPrice} years={years} />
          <div className="metric-value-container">
            <div className="pe10-label">{t("metrics.current_price")}</div>
            <div className="pe10-value">
              {currencySymbol(data.ticker)} {formatNumber(data.currentPrice, 2, locale)}
            </div>
          </div>
          {renderChart(METRIC_IDS.currentPrice)}
        </div>
        <div id={METRIC_IDS.marketCap} {...metricBlockProps(METRIC_IDS.marketCap)}>
          {renderAlertButton(METRIC_IDS.marketCap, t("metrics.market_cap"))}
          <ShareButton metricId={METRIC_IDS.marketCap} years={years} />
          <div className="metric-value-container">
            <div className="pe10-label">{t("metrics.market_cap")} <InfoBtn ariaLabel={moreInfo} onClick={() => open("marketCap")} /></div>
            <div className="pe10-value">
              {data.marketCap !== null ? formatAmount(data.marketCap) : "N/A"}
            </div>
          </div>
          {renderChart(METRIC_IDS.marketCap)}
        </div>
        <div id={METRIC_IDS.yearsOfData} {...metricBlockProps(METRIC_IDS.yearsOfData)}>
          <ShareButton metricId={METRIC_IDS.yearsOfData} years={years} />
          <div className="metric-value-container">
            <div className="pe10-label">{t("metrics.years_of_data")}</div>
            <div className="pe10-value">
              {formatYearsOfData(data.pe10YearsOfData, data.pfcf10YearsOfData)}
            </div>
          </div>
        </div>
      </div>

      {/* ── Section: Dívida ── */}
      {isFinancial ? (
        <div className="card-section">
          <div className="card-section-heading">{t("metrics.debt_section")}</div>
          <p className="card-financial-note">
            {t("metrics.financial_note")}
          </p>
        </div>
      ) : (
      <div className="card-section">
        <div className="card-section-heading">{t("metrics.debt_section")}</div>

        {/* All 5 leverage indicators in one row */}
        <div className="metrics-row leverage-row-5col">
          <div id={METRIC_IDS.debtToEquity} {...metricBlockProps(METRIC_IDS.debtToEquity)}>
            {renderAlertButton(METRIC_IDS.debtToEquity, t("metrics.gross_debt_equity"))}
            <ShareButton metricId={METRIC_IDS.debtToEquity} years={years} />
            <div className="metric-value-container">
              <div className="pe10-label">{t("metrics.gross_debt_equity")} <InfoBtn ariaLabel={moreInfo} onClick={() => open("debtToEquity")} /></div>
              {data.debtToEquity !== null ? (
                <div className="pe10-value">{formatNumber(data.debtToEquity, 2, locale)}</div>
              ) : (
                <div className="pe10-error">{data.leverageError || "N/A"}</div>
              )}
            </div>
            {renderChart(METRIC_IDS.debtToEquity)}
          </div>
          {data.debtExLeaseToEquity !== null && (
            <div id={METRIC_IDS.debtExLease} {...metricBlockProps(METRIC_IDS.debtExLease)}>
              {renderAlertButton(METRIC_IDS.debtExLease, t("metrics.debt_ex_lease_equity"))}
              <ShareButton metricId={METRIC_IDS.debtExLease} years={years} />
              <div className="metric-value-container">
                <div className="pe10-label">{t("metrics.debt_ex_lease_equity")} <InfoBtn ariaLabel={moreInfo} onClick={() => open("debtExLease")} /></div>
                <div className="pe10-value">{formatNumber(data.debtExLeaseToEquity, 2, locale)}</div>
              </div>
              {renderChart(METRIC_IDS.debtExLease)}
            </div>
          )}
          <div id={METRIC_IDS.liabToEquity} {...metricBlockProps(METRIC_IDS.liabToEquity)}>
            {renderAlertButton(METRIC_IDS.liabToEquity, t("metrics.liab_equity"))}
            <ShareButton metricId={METRIC_IDS.liabToEquity} years={years} />
            <div className="metric-value-container">
              <div className="pe10-label">{t("metrics.liab_equity")} <InfoBtn ariaLabel={moreInfo} onClick={() => open("liabToEquity")} /></div>
              {data.liabilitiesToEquity !== null ? (
                <div className="pe10-value">{formatNumber(data.liabilitiesToEquity, 2, locale)}</div>
              ) : (
                <div className="pe10-error">{data.leverageError || "N/A"}</div>
              )}
            </div>
            {renderChart(METRIC_IDS.liabToEquity)}
          </div>
          <div id={METRIC_IDS.debtToEarnings} {...metricBlockProps(METRIC_IDS.debtToEarnings)}>
            {renderAlertButton(METRIC_IDS.debtToEarnings, t("metrics.gross_debt_earnings"))}
            <ShareButton metricId={METRIC_IDS.debtToEarnings} years={years} />
            <div className="metric-value-container">
              <div className="pe10-label">{t("metrics.gross_debt_earnings")} <span className="pe10-label-note">{t("metrics.average")} {data.pe10YearsOfData}{t("common.year_abbrev")}</span> <InfoBtn ariaLabel={moreInfo} onClick={() => open("debtToEarnings")} /></div>
              {data.debtToAvgEarnings !== null ? (
                <div className="pe10-value">{formatNumber(data.debtToAvgEarnings, 1, locale)}</div>
              ) : (
                <div className="pe10-error">N/A</div>
              )}
            </div>
            {renderChart(METRIC_IDS.debtToEarnings)}
          </div>
          <div id={METRIC_IDS.debtToFCF} {...metricBlockProps(METRIC_IDS.debtToFCF)}>
            {renderAlertButton(METRIC_IDS.debtToFCF, t("metrics.gross_debt_fcf"))}
            <ShareButton metricId={METRIC_IDS.debtToFCF} years={years} />
            <div className="metric-value-container">
              <div className="pe10-label">{t("metrics.gross_debt_fcf")} <span className="pe10-label-note">{t("metrics.average")} {data.pfcf10YearsOfData}{t("common.year_abbrev")}</span> <InfoBtn ariaLabel={moreInfo} onClick={() => open("debtToFCF")} /></div>
              {data.debtToAvgFCF !== null ? (
                <div className="pe10-value">{formatNumber(data.debtToAvgFCF, 1, locale)}</div>
              ) : (
                <div className="pe10-error">N/A</div>
              )}
            </div>
            {renderChart(METRIC_IDS.debtToFCF)}
          </div>
        </div>
      </div>
      )}

      {/* ── Section: Preço em relação a resultados ── */}
      <div className="card-section">
        <div className="card-section-heading">{t("metrics.price_vs_results", { years: years, yearLabel: pluralize(years, "common.year_singular", "common.year_plural") })}</div>

        {/* All 6 valuation indicators in one row */}
        <div className="metrics-row valuation-row-6col">
          <div id={METRIC_IDS.pe10} {...metricBlockProps(METRIC_IDS.pe10)}>
            {renderAlertButton(METRIC_IDS.pe10, pl10Label)}
            <ShareButton metricId={METRIC_IDS.pe10} years={years} />
            <div className="metric-value-container">
              <div className="pe10-label">{pl10Label} <InfoBtn ariaLabel={moreInfo} onClick={() => open("pl10")} /></div>
              {data.pe10 !== null ? (
                <div className="pe10-value">{formatNumber(data.pe10, 1, locale)}</div>
              ) : (
                <div className="pe10-error">{translateError(data.pe10Error, t)}</div>
              )}
            </div>
            {renderChart(METRIC_IDS.pe10)}
          </div>
          <div id={METRIC_IDS.peg} {...metricBlockProps(METRIC_IDS.peg)}>
            {renderAlertButton(METRIC_IDS.peg, "PEG")}
            <ShareButton metricId={METRIC_IDS.peg} years={years} />
            <div className="metric-value-container">
              <div className="pe10-label">PEG <span className="pe10-label-note">{t("metrics.lynch")}</span> <InfoBtn ariaLabel={moreInfo} onClick={() => open("peg")} /></div>
              {data.peg !== null ? (
                <div className="pe10-value">{formatNumber(data.peg, 2, locale)}</div>
              ) : (
                <div className="pe10-error">{translateError(data.pegError, t) || "N/A"}</div>
              )}
            </div>
            {renderChart(METRIC_IDS.peg)}
          </div>
          <div id={METRIC_IDS.cagrEarnings} {...metricBlockProps(METRIC_IDS.cagrEarnings)}>
            <ShareButton metricId={METRIC_IDS.cagrEarnings} years={years} />
            <div className="metric-value-container">
              <div className="pe10-label">{t("metrics.cagr_earnings")} <span className="pe10-label-note">{t("metrics.real")}</span> <InfoBtn ariaLabel={moreInfo} onClick={() => open("cagrEarnings")} /></div>
              {data.earningsCAGR !== null ? (
                <div className="pe10-value">{formatNumber(data.earningsCAGR, 1, locale)}%</div>
              ) : (
                <div className="pe10-error">N/A</div>
              )}
            </div>
            {renderChart(METRIC_IDS.cagrEarnings)}
          </div>
          <div id={METRIC_IDS.pfcf10} {...metricBlockProps(METRIC_IDS.pfcf10)}>
            {renderAlertButton(METRIC_IDS.pfcf10, pfcl10Label)}
            <ShareButton metricId={METRIC_IDS.pfcf10} years={years} />
            <div className="metric-value-container">
              <div className="pe10-label">{pfcl10Label} <InfoBtn ariaLabel={moreInfo} onClick={() => open("pfcl10")} /></div>
              {data.pfcf10 !== null ? (
                <div className="pe10-value">{formatNumber(data.pfcf10, 1, locale)}</div>
              ) : (
                <div className="pe10-error">{translateError(data.pfcf10Error, t)}</div>
              )}
            </div>
            {renderChart(METRIC_IDS.pfcf10)}
          </div>
          <div id={METRIC_IDS.pfcfg} {...metricBlockProps(METRIC_IDS.pfcfg)}>
            {renderAlertButton(METRIC_IDS.pfcfg, t("metrics.pfcfg_label"))}
            <ShareButton metricId={METRIC_IDS.pfcfg} years={years} />
            <div className="metric-value-container">
              <div className="pe10-label">{t("metrics.pfcfg_label")} <span className="pe10-label-note">{t("metrics.lynch")}</span> <InfoBtn ariaLabel={moreInfo} onClick={() => open("pfclg")} /></div>
              {data.pfcfPeg !== null ? (
                <div className="pe10-value">{formatNumber(data.pfcfPeg, 2, locale)}</div>
              ) : (
                <div className="pe10-error">{translateError(data.pfcfPegError, t) || "N/A"}</div>
              )}
            </div>
            {renderChart(METRIC_IDS.pfcfg)}
          </div>
          <div id={METRIC_IDS.cagrFCF} {...metricBlockProps(METRIC_IDS.cagrFCF)}>
            <ShareButton metricId={METRIC_IDS.cagrFCF} years={years} />
            <div className="metric-value-container">
              <div className="pe10-label">{t("metrics.cagr_fcf")} <span className="pe10-label-note">{t("metrics.real")}</span> <InfoBtn ariaLabel={moreInfo} onClick={() => open("cagrFCF")} /></div>
              {data.fcfCAGR !== null ? (
                <div className="pe10-value">{formatNumber(data.fcfCAGR, 1, locale)}%</div>
              ) : (
                <div className="pe10-error">N/A</div>
              )}
            </div>
            {renderChart(METRIC_IDS.cagrFCF)}
          </div>
        </div>

      </div>

      {(data.pe10AnnualData || data.pfcf10AnnualData) && (
        <div className="pe10-warning">
          {t("metrics.annual_warning")}
        </div>
      )}

      {activeModal && (
        <Modal
          title={`${MODAL_TITLES[activeModal]?.(data, t, locale) ?? ""} — ${data.name}`}
          onClose={() => setActiveModal(null)}
        >
          <ModalContent modalKey={activeModal} data={data} />
        </Modal>
      )}
    </article>
  );
}

export function CompanyMetricsCardLoading() {
  return (
    <div className="pe10-loading">
      <div className="pe10-loading-bar" />
      <div className="pe10-loading-bar-lg" />
      <div className="pe10-loading-bar-row">
        <div className="pe10-loading-bar-sm" />
        <div className="pe10-loading-bar-sm" />
        <div className="pe10-loading-bar-sm" />
      </div>
    </div>
  );
}
