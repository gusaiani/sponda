import { useMemo } from "react";
import { useFundamentals, type FundamentalsYear } from "../hooks/useFundamentals";
import { inferPeriodsPerYear, trailingQuartersAverage } from "../hooks/deriveForYears";
import { useTranslation } from "../i18n";
import type { TranslationKey } from "../i18n";
import { formatNumber } from "../utils/format";
import type { InflationMode } from "./InflationToggle";
import "../styles/fundamentals.css";

/* ── Augmented row with trailing-window PE ratios ── */

interface AugmentedFundamentalsYear extends FundamentalsYear {
  pe: number | null;
  pfcf: number | null;
}

interface TrailingRatios {
  pe: number | null;
  pfcf: number | null;
}

interface EarningsQuarterDetail {
  end_date: string;
  net_income: number;
}

interface CashFlowQuarterDetail {
  end_date: string;
  fcf: number;
}

interface YearDetail<QuarterDetail> {
  year: number;
  ipcaFactor: number;
  quarters: number;
  quarterlyDetail: QuarterDetail[];
}

/** The slice of the quote payload the ratio columns need — satisfied
 *  structurally by QuoteResult. */
export interface TrailingRatioSource {
  pe10CalculationDetails: YearDetail<EarningsQuarterDetail>[];
  pfcf10CalculationDetails: YearDetail<CashFlowQuarterDetail>[];
  pe10PeriodsPerYear?: number;
  pfcf10PeriodsPerYear?: number;
}

function anchoredTrailingAverage<QuarterDetail extends { end_date: string }>(
  details: YearDetail<QuarterDetail>[],
  anchorYear: number,
  windowYears: number,
  periodsPerYear: number,
  getPeriodNominal: (quarter: QuarterDetail) => number,
): number | null {
  const anchoredDescending = details
    .filter((yearDetail) => yearDetail.year <= anchorYear)
    .sort((a, b) => b.year - a.year);
  const trail = trailingQuartersAverage(
    anchoredDescending,
    windowYears,
    periodsPerYear,
    getPeriodNominal,
    (yearDetail, taken) => ({ ...yearDetail, quarters: taken.length, quarterlyDetail: taken }),
  );
  return trail.hasEnoughData ? trail.avg : null;
}

/**
 * P/L{N} and P/FCL{N} per historical year, computed with the same
 * trailing-window math the Indicadores tab uses — each year's window is
 * exactly N × periodsPerYear filings ending at that year's last filed
 * period. A year without enough trailing history gets null (rendered
 * as "—") instead of a silently-shrunk average. Both the market cap
 * and the averaged figures are in today's purchasing power, which is
 * equivalent to comparing both in that year's money.
 */
export function computeTrailingPERatios(
  data: FundamentalsYear[],
  source: TrailingRatioSource | null,
  windowYears: number,
): Map<number, TrailingRatios> {
  const result = new Map<number, TrailingRatios>();
  const earningsDetails = source?.pe10CalculationDetails ?? [];
  const cashFlowDetails = source?.pfcf10CalculationDetails ?? [];
  const earningsPeriodsPerYear =
    source?.pe10PeriodsPerYear ?? inferPeriodsPerYear(earningsDetails);
  const cashFlowPeriodsPerYear =
    source?.pfcf10PeriodsPerYear ?? inferPeriodsPerYear(cashFlowDetails);

  for (const row of data) {
    const marketCap = row.marketCapAdjusted ?? row.marketCap;
    if (marketCap === null) {
      result.set(row.year, { pe: null, pfcf: null });
      continue;
    }

    const averageEarnings = anchoredTrailingAverage(
      earningsDetails, row.year, windowYears, earningsPeriodsPerYear,
      (quarter) => quarter.net_income,
    );
    const averageFcf = anchoredTrailingAverage(
      cashFlowDetails, row.year, windowYears, cashFlowPeriodsPerYear,
      (quarter) => quarter.fcf,
    );

    const computeRatio = (average: number | null): number | null =>
      average !== null && average !== 0
        ? Math.round((marketCap / average) * 100) / 100
        : null;

    result.set(row.year, {
      pe: computeRatio(averageEarnings),
      pfcf: computeRatio(averageFcf),
    });
  }

  return result;
}

export function augmentWithPERatios(
  data: FundamentalsYear[],
  windowYears: number,
  source: TrailingRatioSource | null,
): AugmentedFundamentalsYear[] {
  const peRatios = computeTrailingPERatios(data, source, windowYears);
  return [...data]
    .sort((a, b) => b.year - a.year)
    .map((row) => {
      const ratios = peRatios.get(row.year) ?? { pe: null, pfcf: null };
      return { ...row, ...ratios };
    });
}

/* ── Column definitions ── */

type ValueMode = InflationMode;

interface ColumnDef {
  key: string;
  label: string;
  group: "balanco" | "resultado" | "caixa" | "retorno";
  format: (row: AugmentedFundamentalsYear, mode: ValueMode) => string | null;
}

function millions(value: number | null, locale: string): string | null {
  if (value === null) return null;
  return formatNumber(value / 1e6, 0, locale);
}

function millionsWithSign(value: number | null, locale: string): string | null {
  if (value === null) return null;
  return formatNumber(value / 1e6, 0, locale);
}

function ratio(value: number | null, locale: string): string | null {
  if (value === null) return null;
  return formatNumber(value, 2, locale);
}

export function getTranslatedColumns(
  t: (key: TranslationKey) => string,
  windowYears: number,
  locale: string,
): ColumnDef[] {
  return [
    // Balanço
    {
      key: "debtExLease", label: t("fundamentals.col.debt"), group: "balanco",
      format: (row, mode) => millions(mode === "adjusted" ? row.debtExLeaseAdjusted : row.debtExLease, locale),
    },
    {
      key: "totalLiabilities", label: t("fundamentals.col.liabilities"), group: "balanco",
      format: (row, mode) => millions(mode === "adjusted" ? row.totalLiabilitiesAdjusted : row.totalLiabilities, locale),
    },
    {
      key: "equity", label: t("fundamentals.col.equity"), group: "balanco",
      format: (row, mode) => millions(mode === "adjusted" ? row.stockholdersEquityAdjusted : row.stockholdersEquity, locale),
    },
    {
      key: "debtToEquity", label: t("fundamentals.col.debt_equity"), group: "balanco",
      format: (row) => ratio(row.debtToEquity, locale),
    },
    {
      key: "liabToEquity", label: t("fundamentals.col.liab_equity"), group: "balanco",
      format: (row) => ratio(row.liabilitiesToEquity, locale),
    },
    {
      key: "currentRatio", label: t("fundamentals.col.current_ratio"), group: "balanco",
      format: (row) => ratio(row.currentRatio, locale),
    },
    // Resultado
    {
      key: "revenue", label: t("fundamentals.col.revenue"), group: "resultado",
      format: (row, mode) => millions(mode === "adjusted" ? row.revenueAdjusted : row.revenue, locale),
    },
    {
      key: "netIncome", label: t("fundamentals.col.net_income"), group: "resultado",
      format: (row, mode) => millionsWithSign(mode === "adjusted" ? row.netIncomeAdjusted : row.netIncome, locale),
    },
    {
      key: "pe", label: `${t("fundamentals.col.pe")}${windowYears}`, group: "resultado",
      format: (row) => ratio(row.pe, locale),
    },
    // Caixa
    {
      key: "fcf", label: t("fundamentals.col.fcf"), group: "caixa",
      format: (row, mode) => millionsWithSign(mode === "adjusted" ? row.fcfAdjusted : row.fcf, locale),
    },
    {
      key: "pfcf", label: `${t("fundamentals.col.pfcf")}${windowYears}`, group: "caixa",
      format: (row) => ratio(row.pfcf, locale),
    },
    {
      key: "operatingCF", label: t("fundamentals.col.operating_cf"), group: "caixa",
      format: (row, mode) => millionsWithSign(mode === "adjusted" ? row.operatingCashFlowAdjusted : row.operatingCashFlow, locale),
    },
    // Retorno
    {
      key: "marketCap", label: t("fundamentals.col.market_cap"), group: "retorno",
      format: (row, mode) => millions(mode === "adjusted" ? row.marketCapAdjusted : row.marketCap, locale),
    },
    {
      key: "dividends", label: t("fundamentals.col.dividends"), group: "retorno",
      format: (row, mode) => {
        const value = mode === "adjusted" ? row.dividendsAdjusted : row.dividendsPaid;
        return millions(value ?? 0, locale);
      },
    },
  ];
}

const BALANCE_COUNT = 6;
const RESULTADO_COUNT = 3;
const CAIXA_COUNT = 3;
const RETORNO_COUNT = 2;

const GROUP_START_INDICES = new Set([
  BALANCE_COUNT,
  BALANCE_COUNT + RESULTADO_COUNT,
  BALANCE_COUNT + RESULTADO_COUNT + CAIXA_COUNT,
]);

/* ── Component ── */

interface Props {
  ticker: string;
  years: number;
  valueMode: ValueMode;
  /** Quote payload holding the per-filing calculation details the
   *  ratio columns are computed from. Null while it loads. */
  quote: TrailingRatioSource | null;
}

export function FundamentalsTab({ ticker, years, valueMode, quote }: Props) {
  const { data: response, isLoading, error } = useFundamentals(ticker, true);
  const rawData = response?.years;
  const { t, locale } = useTranslation();
  const columns = useMemo(() => getTranslatedColumns(t, years, locale), [t, years, locale]);
  const data = useMemo(
    () => (rawData ? augmentWithPERatios(rawData, years, quote) : null),
    [rawData, years, quote],
  );
  // A "partial year" depends on the filing frequency: 3 quarters is
  // partial for a quarterly reporter, but 2 filings IS a complete year
  // for a semi-annual one like RIO (whose rows all wore a bogus "2T"
  // badge before).
  const periodsPerYear =
    quote?.pe10PeriodsPerYear ?? (rawData ? inferPeriodsPerYear(rawData) : 4);
  const partialYearSuffix = periodsPerYear === 2 ? "S" : "T";

  if (isLoading) return <FundamentalsTabLoading />;
  if (error) {
    return (
      <div className="fundamentals-container">
        <div className="fundamentals-error">{(error as Error).message}</div>
      </div>
    );
  }
  if (!data || data.length === 0) {
    return (
      <div className="fundamentals-container">
        <div className="fundamentals-error">{t("fundamentals.no_data")}</div>
      </div>
    );
  }

  return (
    <div className="fundamentals-container">
      <div className="fundamentals-scroll-wrapper">
        <table className="fundamentals-table">
          <thead>
            {/* Group header row */}
            <tr className="fundamentals-group-row">
              <th className="fundamentals-sticky-col" />
              <th colSpan={BALANCE_COUNT}>{t("fundamentals.balance")}</th>
              <th colSpan={RESULTADO_COUNT} className="fundamentals-group-separator">{t("fundamentals.income")}</th>
              <th colSpan={CAIXA_COUNT} className="fundamentals-group-separator">{t("fundamentals.cash_flow")}</th>
              <th colSpan={RETORNO_COUNT} className="fundamentals-group-separator">{t("fundamentals.returns")}</th>
            </tr>
            {/* Column header row */}
            <tr>
              <th className="fundamentals-sticky-col">{t("fundamentals.year")}</th>
              {columns.map((col, index) => (
                <th
                  key={col.key}
                  className={GROUP_START_INDICES.has(index) ? "fundamentals-group-separator" : undefined}
                >
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((row) => (
              <tr key={row.year}>
                <td className="fundamentals-sticky-col">
                  <span className="fundamentals-year">{row.year}</span>
                  {row.quarters > 0 && row.quarters < periodsPerYear && (
                    <span className="fundamentals-partial">{row.quarters}{partialYearSuffix}</span>
                  )}
                </td>
                {columns.map((col, index) => {
                  const formatted = col.format(row, valueMode);
                  const separatorClass = GROUP_START_INDICES.has(index) ? "fundamentals-group-separator" : "";
                  if (formatted === null) {
                    return (
                      <td key={col.key} className={separatorClass || undefined}>
                        <span className="fundamentals-null">—</span>
                      </td>
                    );
                  }
                  const rawValue = getRawValue(row, col.key, valueMode);
                  const isNegative = rawValue !== null && rawValue < 0;
                  const cellClass = [isNegative ? "fundamentals-negative" : "", separatorClass].filter(Boolean).join(" ");
                  return (
                    <td key={col.key} className={cellClass || undefined}>
                      {formatted}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function getRawValue(row: AugmentedFundamentalsYear, key: string, mode: ValueMode): number | null {
  switch (key) {
    case "debtExLease": return mode === "adjusted" ? row.debtExLeaseAdjusted : row.debtExLease;
    case "totalLiabilities": return mode === "adjusted" ? row.totalLiabilitiesAdjusted : row.totalLiabilities;
    case "equity": return mode === "adjusted" ? row.stockholdersEquityAdjusted : row.stockholdersEquity;
    case "debtToEquity": return row.debtToEquity;
    case "liabToEquity": return row.liabilitiesToEquity;
    case "currentRatio": return row.currentRatio;
    case "revenue": return mode === "adjusted" ? row.revenueAdjusted : row.revenue;
    case "netIncome": return mode === "adjusted" ? row.netIncomeAdjusted : row.netIncome;
    case "pe": return row.pe;
    case "pfcf": return row.pfcf;
    case "fcf": return mode === "adjusted" ? row.fcfAdjusted : row.fcf;
    case "operatingCF": return mode === "adjusted" ? row.operatingCashFlowAdjusted : row.operatingCashFlow;
    case "marketCap": return mode === "adjusted" ? row.marketCapAdjusted : row.marketCap;
    case "dividends": return mode === "adjusted" ? row.dividendsAdjusted : row.dividendsPaid;
    default: return null;
  }
}

export function FundamentalsTabLoading() {
  return (
    <div className="fundamentals-loading">
      <div className="fundamentals-loading-bar" />
      <div className="fundamentals-loading-bar-sm" />
      <div className="fundamentals-loading-bar-sm" />
      <div className="fundamentals-loading-bar-sm" />
      <div className="fundamentals-loading-bar-sm" />
      <div className="fundamentals-loading-bar-sm" />
    </div>
  );
}
