import { useState, useMemo } from "react";
import { useFundamentals, type FundamentalsYear } from "../hooks/useFundamentals";
import { useTranslation } from "../i18n";
import type { TranslationKey } from "../i18n";
import { br } from "../utils/format";
import { isBrazilianTicker } from "../utils/ticker";
import "../styles/fundamentals.css";

/* ── Augmented row with Shiller PE ratios ── */

interface AugmentedFundamentalsYear extends FundamentalsYear {
  pe10: number | null;
  pe5: number | null;
  pfcl10: number | null;
  pfcl5: number | null;
}

interface ShillerRatios {
  pe10: number | null;
  pe5: number | null;
  pfcl10: number | null;
  pfcl5: number | null;
}

export function computeShillerPERatios(
  data: FundamentalsYear[],
): Map<number, ShillerRatios> {
  const sortedAscending = [...data].sort((a, b) => a.year - b.year);
  const result = new Map<number, ShillerRatios>();

  for (const row of sortedAscending) {
    if (row.marketCap === null) {
      result.set(row.year, { pe10: null, pe5: null, pfcl10: null, pfcl5: null });
      continue;
    }

    const getAverageValues = (
      windowYears: number,
      accessor: (r: FundamentalsYear) => number | null,
    ): number | null => {
      const relevantValues = sortedAscending
        .filter((r) => r.year <= row.year && r.year > row.year - windowYears)
        .map(accessor)
        .filter((value): value is number => value !== null);
      if (relevantValues.length === 0) return null;
      const average =
        relevantValues.reduce((sum, value) => sum + value, 0) /
        relevantValues.length;
      return average !== 0 ? average : null;
    };

    const averageEarnings10 = getAverageValues(10, (r) => r.netIncomeAdjusted);
    const averageEarnings5 = getAverageValues(5, (r) => r.netIncomeAdjusted);
    const averageFcf10 = getAverageValues(10, (r) => r.fcfAdjusted);
    const averageFcf5 = getAverageValues(5, (r) => r.fcfAdjusted);

    const computeRatio = (average: number | null): number | null =>
      average !== null ? Math.round((row.marketCap! / average) * 10) / 10 : null;

    result.set(row.year, {
      pe10: computeRatio(averageEarnings10),
      pe5: computeRatio(averageEarnings5),
      pfcl10: computeRatio(averageFcf10),
      pfcl5: computeRatio(averageFcf5),
    });
  }

  return result;
}

export function augmentWithPERatios(
  data: FundamentalsYear[],
): AugmentedFundamentalsYear[] {
  const peRatios = computeShillerPERatios(data);
  return [...data]
    .sort((a, b) => b.year - a.year)
    .map((row) => {
      const ratios = peRatios.get(row.year) ?? { pe10: null, pe5: null, pfcl10: null, pfcl5: null };
      return { ...row, ...ratios };
    });
}

/* ── Column definitions ── */

type ValueMode = "nominal" | "adjusted";

interface ColumnDef {
  key: string;
  label: string;
  group: "balanco" | "resultado" | "caixa" | "retorno";
  format: (row: AugmentedFundamentalsYear, mode: ValueMode) => string | null;
}

function millions(value: number | null): string | null {
  if (value === null) return null;
  return br(value / 1e6, 0);
}

function millionsWithSign(value: number | null): string | null {
  if (value === null) return null;
  const formatted = br(value / 1e6, 0);
  return value < 0 ? formatted : formatted;
}

function ratio(value: number | null): string | null {
  if (value === null) return null;
  return br(value, 2);
}

function getTranslatedColumns(t: (key: TranslationKey) => string): ColumnDef[] {
  return [
    // Balanço
    {
      key: "debtExLease", label: t("fundamentals.col.debt"), group: "balanco",
      format: (row, mode) => millions(mode === "adjusted" ? row.debtExLeaseAdjusted : row.debtExLease),
    },
    {
      key: "totalLiabilities", label: t("fundamentals.col.liabilities"), group: "balanco",
      format: (row, mode) => millions(mode === "adjusted" ? row.totalLiabilitiesAdjusted : row.totalLiabilities),
    },
    {
      key: "equity", label: t("fundamentals.col.equity"), group: "balanco",
      format: (row, mode) => millions(mode === "adjusted" ? row.stockholdersEquityAdjusted : row.stockholdersEquity),
    },
    {
      key: "debtToEquity", label: t("fundamentals.col.debt_equity"), group: "balanco",
      format: (row) => ratio(row.debtToEquity),
    },
    {
      key: "liabToEquity", label: t("fundamentals.col.liab_equity"), group: "balanco",
      format: (row) => ratio(row.liabilitiesToEquity),
    },
    {
      key: "currentRatio", label: t("fundamentals.col.current_ratio"), group: "balanco",
      format: (row) => ratio(row.currentRatio),
    },
    // Resultado
    {
      key: "revenue", label: t("fundamentals.col.revenue"), group: "resultado",
      format: (row, mode) => millions(mode === "adjusted" ? row.revenueAdjusted : row.revenue),
    },
    {
      key: "netIncome", label: t("fundamentals.col.net_income"), group: "resultado",
      format: (row, mode) => millionsWithSign(mode === "adjusted" ? row.netIncomeAdjusted : row.netIncome),
    },
    {
      key: "pe10", label: t("fundamentals.col.pe10"), group: "resultado",
      format: (row) => ratio(row.pe10),
    },
    {
      key: "pe5", label: t("fundamentals.col.pe5"), group: "resultado",
      format: (row) => ratio(row.pe5),
    },
    // Caixa
    {
      key: "fcf", label: t("fundamentals.col.fcf"), group: "caixa",
      format: (row, mode) => millionsWithSign(mode === "adjusted" ? row.fcfAdjusted : row.fcf),
    },
    {
      key: "pfcl10", label: t("fundamentals.col.pfcf10"), group: "caixa",
      format: (row) => ratio(row.pfcl10),
    },
    {
      key: "pfcl5", label: t("fundamentals.col.pfcf5"), group: "caixa",
      format: (row) => ratio(row.pfcl5),
    },
    {
      key: "operatingCF", label: t("fundamentals.col.operating_cf"), group: "caixa",
      format: (row, mode) => millionsWithSign(mode === "adjusted" ? row.operatingCashFlowAdjusted : row.operatingCashFlow),
    },
    // Retorno
    {
      key: "marketCap", label: t("fundamentals.col.market_cap"), group: "retorno",
      format: (row, mode) => millions(mode === "adjusted" ? row.marketCapAdjusted : row.marketCap),
    },
    {
      key: "dividends", label: t("fundamentals.col.dividends"), group: "retorno",
      format: (row, mode) => {
        const value = mode === "adjusted" ? row.dividendsAdjusted : row.dividendsPaid;
        return millions(value ?? 0);
      },
    },
  ];
}

const BALANCE_COUNT = 6;
const RESULTADO_COUNT = 4;
const CAIXA_COUNT = 4;
const RETORNO_COUNT = 2;

const GROUP_START_INDICES = new Set([
  BALANCE_COUNT,
  BALANCE_COUNT + RESULTADO_COUNT,
  BALANCE_COUNT + RESULTADO_COUNT + CAIXA_COUNT,
]);

/* ── Component ── */

interface Props {
  ticker: string;
}

export function FundamentalsTab({ ticker }: Props) {
  const { data: rawData, isLoading, error } = useFundamentals(ticker, true);
  const { t } = useTranslation();
  const [valueMode, setValueMode] = useState<ValueMode>("nominal");
  const columns = useMemo(() => getTranslatedColumns(t), [t]);
  const data = useMemo(
    () => (rawData ? augmentWithPERatios(rawData) : null),
    [rawData],
  );

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
      <div className="fundamentals-toggle-wrapper">
        <button
          className={`fundamentals-toggle-pill ${valueMode === "nominal" ? "fundamentals-toggle-pill-active" : ""}`}
          onClick={() => setValueMode(valueMode === "nominal" ? "adjusted" : "nominal")}
        >
          {t("fundamentals.nominal")}
        </button>
        <button
          className={`fundamentals-toggle-pill ${valueMode === "adjusted" ? "fundamentals-toggle-pill-active" : ""}`}
          onClick={() => setValueMode(valueMode === "adjusted" ? "nominal" : "adjusted")}
        >
          {isBrazilianTicker(ticker) ? t("fundamentals.ipca") : t("fundamentals.cpi")}
        </button>
      </div>

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
                  {row.quarters > 0 && row.quarters < 4 && (
                    <span className="fundamentals-partial">{row.quarters}T</span>
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
    case "pe10": return row.pe10;
    case "pe5": return row.pe5;
    case "pfcl10": return row.pfcl10;
    case "pfcl5": return row.pfcl5;
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
