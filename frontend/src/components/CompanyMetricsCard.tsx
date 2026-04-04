import { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import "../styles/card.css";
import { useTranslation, type TranslationKey } from "../i18n";
import { isBrazilianTicker } from "../utils/ticker";

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
}

const FINANCIAL_SECTORS = new Set(["Finance", "Financial Services"]);

type ModalKey =
  | "debtToEquity" | "debtExLease" | "liabToEquity"
  | "debtToEarnings" | "debtToFCF"
  | "pl10" | "peg" | "cagrEarnings"
  | "pfcl10" | "pfclg" | "cagrFCF"
  | null;

import { ptLabel, br, formatLargeNumber, formatQuarterLabel } from "../utils/format";

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

/* ── Balance sheet components helper ── */

function BalanceSheetComponents({ data }: { data: QuoteData }) {
  const { t } = useTranslation();
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
            <span className="pe10-calc-formula-val">{formatLargeNumber(data.totalDebt)}</span>
          </div>
        )}
        {data.totalLease !== null && (
          <div className="pe10-calc-formula">
            <span>{t("modal.leases")}</span>
            <span className="pe10-calc-formula-val">{formatLargeNumber(data.totalLease)}</span>
          </div>
        )}
        {data.totalLiabilities !== null && (
          <div className="pe10-calc-formula">
            <span>{t("modal.total_liabilities")}</span>
            <span className="pe10-calc-formula-val">{formatLargeNumber(data.totalLiabilities)}</span>
          </div>
        )}
        <div className="pe10-calc-formula">
          <span>{t("modal.equity")}</span>
          <span className="pe10-calc-formula-val">{formatLargeNumber(data.stockholdersEquity)}</span>
        </div>
      </div>
    </div>
  );
}

/* ── Per-metric modal content ── */

function DebtToEquityInfo({ data }: { data: QuoteData }) {
  const { t } = useTranslation();
  return (
    <>
      <div className="modal-explainer">
        <p>{t("modal.debt_equity_explain")}</p>
        <p>{t("modal.debt_equity_compare")}</p>
      </div>
      <BalanceSheetComponents data={data} />
      {data.debtToEquity !== null && data.stockholdersEquity !== null && (
        <div className="pe10-calc-details">
          <div className="pe10-calc-section">
            <div className="pe10-calc-section-title">{t("modal.calculation")}</div>
            <div className="pe10-calc-formula">
              <span>{formatLargeNumber(data.totalDebt!)} ÷ {formatLargeNumber(data.stockholdersEquity)}</span>
              <span className="pe10-calc-formula-val">= {br(data.debtToEquity, 2)}</span>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function DebtExLeaseInfo({ data }: { data: QuoteData }) {
  const { t } = useTranslation();
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
              <span>({formatLargeNumber(data.totalDebt)} − {formatLargeNumber(data.totalLease ?? 0)}) ÷ {formatLargeNumber(data.stockholdersEquity)}</span>
              <span className="pe10-calc-formula-val">= {br(data.debtExLeaseToEquity, 2)}</span>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function LiabToEquityInfo({ data }: { data: QuoteData }) {
  const { t } = useTranslation();
  return (
    <>
      <div className="modal-explainer">
        <p>{t("modal.liab_equity_explain")}</p>
        <p>{t("modal.liab_equity_broader")}</p>
      </div>
      <BalanceSheetComponents data={data} />
      {data.liabilitiesToEquity !== null && data.stockholdersEquity !== null && (
        <div className="pe10-calc-details">
          <div className="pe10-calc-section">
            <div className="pe10-calc-section-title">{t("modal.calculation")}</div>
            <div className="pe10-calc-formula">
              <span>{formatLargeNumber(data.totalLiabilities!)} ÷ {formatLargeNumber(data.stockholdersEquity)}</span>
              <span className="pe10-calc-formula-val">= {br(data.liabilitiesToEquity, 2)}</span>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function DebtToEarningsInfo({ data }: { data: QuoteData }) {
  const { t } = useTranslation();
  return (
    <>
      <div className="modal-explainer">
        <p>{t("modal.debt_earnings_explain")}</p>
        <p>{t("modal.debt_earnings_note")}</p>
      </div>
      {data.totalDebt !== null && data.debtToAvgEarnings !== null && data.avgAdjustedNetIncome !== null && (
        <div className="pe10-calc-details">
          <div className="pe10-calc-section">
            <div className="pe10-calc-section-title">{t("modal.calculation")}</div>
            <div className="pe10-calc-formula">
              <span>{t("modal.gross_debt")}</span>
              <span className="pe10-calc-formula-val">{formatLargeNumber(data.totalDebt)}</span>
            </div>
            <div className="pe10-calc-formula">
              <span>{t("modal.pl10_avg_label", { years: data.pe10YearsOfData })}</span>
              <span className="pe10-calc-formula-val">{formatLargeNumber(data.avgAdjustedNetIncome)}</span>
            </div>
            <div className="pe10-calc-formula pe10-calc-result">
              <span>{formatLargeNumber(data.totalDebt)} ÷ {formatLargeNumber(data.avgAdjustedNetIncome)}</span>
              <span className="pe10-calc-formula-val">= {br(data.debtToAvgEarnings, 2)}</span>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function DebtToFCFInfo({ data }: { data: QuoteData }) {
  const { t } = useTranslation();
  return (
    <>
      <div className="modal-explainer">
        <p>{t("modal.debt_fcf_explain")}</p>
      </div>
      {data.totalDebt !== null && data.debtToAvgFCF !== null && data.avgAdjustedFCF !== null && (
        <div className="pe10-calc-details">
          <div className="pe10-calc-section">
            <div className="pe10-calc-section-title">{t("modal.calculation")}</div>
            <div className="pe10-calc-formula">
              <span>{t("modal.gross_debt")}</span>
              <span className="pe10-calc-formula-val">{formatLargeNumber(data.totalDebt)}</span>
            </div>
            <div className="pe10-calc-formula">
              <span>{t("modal.pfcl10_avg_label", { years: data.pfcf10YearsOfData })}</span>
              <span className="pe10-calc-formula-val">{formatLargeNumber(data.avgAdjustedFCF)}</span>
            </div>
            <div className="pe10-calc-formula pe10-calc-result">
              <span>{formatLargeNumber(data.totalDebt)} ÷ {formatLargeNumber(data.avgAdjustedFCF)}</span>
              <span className="pe10-calc-formula-val">= {br(data.debtToAvgFCF, 2)}</span>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function PL10Info({ data }: { data: QuoteData }) {
  const { t } = useTranslation();
  const [expandedYear, setExpandedYear] = useState<number | null>(null);
  const label = ptLabel(data.pe10Label);
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
                      <td>{formatLargeNumber(year.nominalNetIncome)}</td>
                      <td>{br(year.ipcaFactor, 4)}×</td>
                      <td>{formatLargeNumber(year.adjustedNetIncome)}</td>
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
                        <td colSpan={4}>{t("modal.quarterly_net_income", { value: formatLargeNumber(q.net_income) })}</td>
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
              <span className="pe10-calc-formula-val">{formatLargeNumber(total)}</span>
            </div>
            <div className="pe10-calc-formula">
              <span>÷ {data.pe10YearsOfData} {t("common.year_plural")}</span>
              <span className="pe10-calc-formula-val">
                = {data.avgAdjustedNetIncome !== null ? formatLargeNumber(data.avgAdjustedNetIncome) : "N/A"}
              </span>
            </div>
          </div>

          {data.pe10 !== null && data.avgAdjustedNetIncome !== null && data.marketCap !== null && (
            <div className="pe10-calc-section">
              <div className="pe10-calc-section-title">{t("modal.pl10_step3", { label })}</div>
              <div className="pe10-calc-formula">
                <span>{t("modal.pl10_market_cap")}</span>
                <span className="pe10-calc-formula-val">{formatLargeNumber(data.marketCap)}</span>
              </div>
              <div className="pe10-calc-formula">
                <span>÷ {t("modal.pl10_divided_by")}</span>
                <span className="pe10-calc-formula-val">{formatLargeNumber(data.avgAdjustedNetIncome)}</span>
              </div>
              <div className="pe10-calc-formula pe10-calc-result">
                <span>= {label}</span>
                <span className="pe10-calc-formula-val">{br(data.pe10, 2)}</span>
              </div>
            </div>
          )}
        </div>
      )}
    </>
  );
}

function PFCL10Info({ data }: { data: QuoteData }) {
  const { t } = useTranslation();
  const [expandedYear, setExpandedYear] = useState<number | null>(null);
  const label = ptLabel(data.pfcf10Label);
  const hasCalc = data.pfcf10CalculationDetails.length > 0;
  const total = hasCalc
    ? data.pfcf10CalculationDetails.reduce((s, y) => s + y.adjustedFCF, 0)
    : 0;

  return (
    <>
      <div className="modal-explainer">
        <p>{t("modal.pfcl10_explain", { label })}</p>
        <p>{t("modal.pfcl10_compare", { pfclLabel: label, peLabel: ptLabel(data.pe10Label) })}</p>
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
                      <td>{formatLargeNumber(year.nominalFCF)}</td>
                      <td>{br(year.ipcaFactor, 4)}×</td>
                      <td>{formatLargeNumber(year.adjustedFCF)}</td>
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
                          {t("modal.quarterly_operating", { value: formatLargeNumber(q.operating_cash_flow) })}
                          {" · "}
                          {t("modal.quarterly_investing", { value: formatLargeNumber(q.investment_cash_flow) })}
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
              <span className="pe10-calc-formula-val">{formatLargeNumber(total)}</span>
            </div>
            <div className="pe10-calc-formula">
              <span>÷ {data.pfcf10YearsOfData} {t("common.year_plural")}</span>
              <span className="pe10-calc-formula-val">
                = {data.avgAdjustedFCF !== null ? formatLargeNumber(data.avgAdjustedFCF) : "N/A"}
              </span>
            </div>
          </div>

          {data.pfcf10 !== null && data.avgAdjustedFCF !== null && data.marketCap !== null && (
            <div className="pe10-calc-section">
              <div className="pe10-calc-section-title">{t("modal.pl10_step3", { label })}</div>
              <div className="pe10-calc-formula">
                <span>{t("modal.pl10_market_cap")}</span>
                <span className="pe10-calc-formula-val">{formatLargeNumber(data.marketCap)}</span>
              </div>
              <div className="pe10-calc-formula">
                <span>÷ {t("modal.pfcl10_divided_by")}</span>
                <span className="pe10-calc-formula-val">{formatLargeNumber(data.avgAdjustedFCF)}</span>
              </div>
              <div className="pe10-calc-formula pe10-calc-result">
                <span>= {label}</span>
                <span className="pe10-calc-formula-val">{br(data.pfcf10, 2)}</span>
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
  const label = isEarnings ? "PEG" : "PFCLG";
  const baseLabel = isEarnings ? ptLabel(data.pe10Label) : ptLabel(data.pfcf10Label);
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
              <span className="pe10-calc-formula-val">{br(baseValue, 2)}</span>
            </div>
            <div className="pe10-calc-formula">
              <span>CAGR {isEarnings ? t("modal.cagr_real_earnings") : t("modal.cagr_real_fcf")}{method === "regression" ? ` (${locale === "pt" ? "regressão" : "regression"})` : ""}</span>
              <span className="pe10-calc-formula-val">{br(cagr, 2)}%</span>
            </div>
            <div className="pe10-calc-formula pe10-calc-result">
              <span>{br(baseValue, 2)} ÷ {br(cagr, 2)}</span>
              <span className="pe10-calc-formula-val">= {br(peg, 2)}</span>
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
              <span className="pe10-calc-formula-val">{br(cagr, 2)}%</span>
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
    case "pl10": return <PL10Info data={data} />;
    case "peg": return <PEGInfo data={data} variant="earnings" />;
    case "cagrEarnings": return <CAGRInfo data={data} variant="earnings" />;
    case "pfcl10": return <PFCL10Info data={data} />;
    case "pfclg": return <PEGInfo data={data} variant="fcf" />;
    case "cagrFCF": return <CAGRInfo data={data} variant="fcf" />;
    default: return null;
  }
}

const MODAL_TITLES: Record<string, (data: QuoteData, t: (key: TranslationKey, params?: Record<string, string | number>) => string) => string> = {
  debtToEquity: (_d, t) => t("modal.title.debt_equity"),
  debtExLease: (_d, t) => t("modal.title.debt_ex_lease"),
  liabToEquity: (_d, t) => t("modal.title.liab_equity"),
  debtToEarnings: (_d, t) => t("modal.title.debt_earnings"),
  debtToFCF: (_d, t) => t("modal.title.debt_fcf"),
  pl10: (d) => ptLabel(d.pe10Label),
  peg: (_d, t) => t("modal.title.peg"),
  cagrEarnings: (_d, t) => t("modal.title.cagr_earnings"),
  pfcl10: (d) => ptLabel(d.pfcf10Label),
  pfclg: (_d, t) => t("modal.title.pfclg"),
  cagrFCF: (_d, t) => t("modal.title.cagr_fcf"),
};

/* ── Main Card ── */

export function CompanyMetricsCard({ data, years, maxYears, onYearsChange, sector }: CompanyMetricsCardProps) {
  const { t, pluralize } = useTranslation();
  const [activeModal, setActiveModal] = useState<ModalKey>(null);

  const pl10Label = ptLabel(data.pe10Label);
  const pfcl10Label = ptLabel(data.pfcf10Label);
  const open = (key: ModalKey) => setActiveModal(key);
  const isFinancial = sector ? FINANCIAL_SECTORS.has(sector) : false;
  const moreInfo = t("metrics.more_info");

  return (
    <article className="pe10-card" aria-label={`${data.name} (${data.ticker})`}>
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
          <div className="metric-block">
            <div className="metric-value-container">
              <div className="pe10-label">{t("metrics.gross_debt_equity")} <InfoBtn ariaLabel={moreInfo} onClick={() => open("debtToEquity")} /></div>
              {data.debtToEquity !== null ? (
                <div className="pe10-value">{br(data.debtToEquity, 2)}</div>
              ) : (
                <div className="pe10-error">{data.leverageError || "N/A"}</div>
              )}
            </div>
          </div>
          {data.debtExLeaseToEquity !== null && (
            <div className="metric-block">
              <div className="metric-value-container">
                <div className="pe10-label">{t("metrics.debt_ex_lease_equity")} <InfoBtn ariaLabel={moreInfo} onClick={() => open("debtExLease")} /></div>
                <div className="pe10-value">{br(data.debtExLeaseToEquity, 2)}</div>
              </div>
            </div>
          )}
          <div className="metric-block">
            <div className="metric-value-container">
              <div className="pe10-label">{t("metrics.liab_equity")} <InfoBtn ariaLabel={moreInfo} onClick={() => open("liabToEquity")} /></div>
              {data.liabilitiesToEquity !== null ? (
                <div className="pe10-value">{br(data.liabilitiesToEquity, 2)}</div>
              ) : (
                <div className="pe10-error">{data.leverageError || "N/A"}</div>
              )}
            </div>
          </div>
          <div className="metric-block">
            <div className="metric-value-container">
              <div className="pe10-label">{t("metrics.gross_debt_earnings")} <span className="pe10-label-note">{t("metrics.average")} {data.pe10YearsOfData}a</span> <InfoBtn ariaLabel={moreInfo} onClick={() => open("debtToEarnings")} /></div>
              {data.debtToAvgEarnings !== null ? (
                <div className="pe10-value">{br(data.debtToAvgEarnings, 1)}</div>
              ) : (
                <div className="pe10-error">N/A</div>
              )}
            </div>
          </div>
          <div className="metric-block">
            <div className="metric-value-container">
              <div className="pe10-label">{t("metrics.gross_debt_fcf")} <span className="pe10-label-note">{t("metrics.average")} {data.pfcf10YearsOfData}a</span> <InfoBtn ariaLabel={moreInfo} onClick={() => open("debtToFCF")} /></div>
              {data.debtToAvgFCF !== null ? (
                <div className="pe10-value">{br(data.debtToAvgFCF, 1)}</div>
              ) : (
                <div className="pe10-error">N/A</div>
              )}
            </div>
          </div>
        </div>
      </div>
      )}

      {/* ── Section: Preço em relação a resultados ── */}
      <div className="card-section">
        <div className="card-section-heading">{t("metrics.price_vs_results", { years: years, yearLabel: pluralize(years, "common.year_singular", "common.year_plural") })}</div>

        {/* All 6 valuation indicators in one row */}
        <div className="metrics-row valuation-row-6col">
          <div className="metric-block">
            <div className="metric-value-container">
              <div className="pe10-label">{pl10Label} <InfoBtn ariaLabel={moreInfo} onClick={() => open("pl10")} /></div>
              {data.pe10 !== null ? (
                <div className="pe10-value">{br(data.pe10, 1)}</div>
              ) : (
                <div className="pe10-error">{data.pe10Error}</div>
              )}
            </div>
          </div>
          <div className="metric-block">
            <div className="metric-value-container">
              <div className="pe10-label">PEG <span className="pe10-label-note">{t("metrics.lynch")}</span> <InfoBtn ariaLabel={moreInfo} onClick={() => open("peg")} /></div>
              {data.peg !== null ? (
                <div className="pe10-value">{br(data.peg, 2)}</div>
              ) : (
                <div className="pe10-error">{data.pegError || "N/A"}</div>
              )}
            </div>
          </div>
          <div className="metric-block">
            <div className="metric-value-container">
              <div className="pe10-label">{t("metrics.cagr_earnings")} <span className="pe10-label-note">{t("metrics.real")}</span> <InfoBtn ariaLabel={moreInfo} onClick={() => open("cagrEarnings")} /></div>
              {data.earningsCAGR !== null ? (
                <div className="pe10-value">{br(data.earningsCAGR, 1)}%</div>
              ) : (
                <div className="pe10-error">N/A</div>
              )}
            </div>
          </div>
          <div className="metric-block">
            <div className="metric-value-container">
              <div className="pe10-label">{pfcl10Label} <InfoBtn ariaLabel={moreInfo} onClick={() => open("pfcl10")} /></div>
              {data.pfcf10 !== null ? (
                <div className="pe10-value">{br(data.pfcf10, 1)}</div>
              ) : (
                <div className="pe10-error">{data.pfcf10Error}</div>
              )}
            </div>
          </div>
          <div className="metric-block">
            <div className="metric-value-container">
              <div className="pe10-label">PFCLG <span className="pe10-label-note">{t("metrics.lynch")}</span> <InfoBtn ariaLabel={moreInfo} onClick={() => open("pfclg")} /></div>
              {data.pfcfPeg !== null ? (
                <div className="pe10-value">{br(data.pfcfPeg, 2)}</div>
              ) : (
                <div className="pe10-error">{data.pfcfPegError || "N/A"}</div>
              )}
            </div>
          </div>
          <div className="metric-block">
            <div className="metric-value-container">
              <div className="pe10-label">{t("metrics.cagr_fcf")} <span className="pe10-label-note">{t("metrics.real")}</span> <InfoBtn ariaLabel={moreInfo} onClick={() => open("cagrFCF")} /></div>
              {data.fcfCAGR !== null ? (
                <div className="pe10-value">{br(data.fcfCAGR, 1)}%</div>
              ) : (
                <div className="pe10-error">N/A</div>
              )}
            </div>
          </div>
        </div>

        {/* Years slider */}
        {maxYears > 1 && (
          <div className="years-slider">
            <div className="years-slider-track">
              <span className="years-slider-bound">1</span>
              <input
                id="years-range"
                type="range"
                min={1}
                max={maxYears}
                step={1}
                value={years}
                onChange={(e) => onYearsChange(Number(e.target.value))}
                className="years-slider-input"
              />
              <span className="years-slider-bound">{maxYears}</span>
            </div>
            <p className="years-slider-caption">
              {t("metrics.slider_caption")} <strong>{years} {pluralize(years, "common.year_singular", "common.year_plural")}</strong> {t("metrics.slider_drag_hint")}
            </p>
          </div>
        )}
      </div>

      {(data.pe10AnnualData || data.pfcf10AnnualData) && (
        <div className="pe10-warning">
          {t("metrics.annual_warning")}
        </div>
      )}

      <div className="pe10-details">
        <div className="pe10-detail-item">
          <div className="pe10-detail-label">{t("metrics.current_price")}</div>
          <div className="pe10-detail-value">
            R$ {br(data.currentPrice, 2)}
          </div>
        </div>
        <div className="pe10-detail-item">
          <div className="pe10-detail-label">{t("metrics.market_cap")}</div>
          <div className="pe10-detail-value">
            {data.marketCap !== null ? formatLargeNumber(data.marketCap) : "N/A"}
          </div>
        </div>
        <div className="pe10-detail-item">
          <div className="pe10-detail-label">{t("metrics.years_of_data")}</div>
          <div className="pe10-detail-value">
            {data.pe10YearsOfData === data.pfcf10YearsOfData
              ? data.pe10YearsOfData
              : `${data.pe10YearsOfData} / ${data.pfcf10YearsOfData}`}
          </div>
        </div>
      </div>

      {activeModal && (
        <Modal
          title={`${MODAL_TITLES[activeModal]?.(data, t) ?? ""} — ${data.name}`}
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
