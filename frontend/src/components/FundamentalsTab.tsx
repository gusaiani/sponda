import { useState, useMemo } from "react";
import { useFundamentals, type FundamentalsYear } from "../hooks/useFundamentals";
import { br } from "../utils/format";
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

function augmentWithPERatios(
  data: FundamentalsYear[],
): AugmentedFundamentalsYear[] {
  const peRatios = computeShillerPERatios(data);
  return data.map((row) => {
    const ratios = peRatios.get(row.year) ?? { pe10: null, pe5: null, pfcl10: null, pfcl5: null };
    return { ...row, ...ratios };
  });
}

/* ── Column definitions ── */

type ValueMode = "nominal" | "adjusted";

interface ColumnDef {
  key: string;
  label: string;
  group: "balanco" | "resultado" | "caixa";
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

const COLUMNS: ColumnDef[] = [
  // Balanço
  {
    key: "debtExLease", label: "Dívida (M)", group: "balanco",
    format: (row, mode) => millions(mode === "adjusted" ? row.debtExLeaseAdjusted : row.debtExLease),
  },
  {
    key: "totalLiabilities", label: "Passivo (M)", group: "balanco",
    format: (row, mode) => millions(mode === "adjusted" ? row.totalLiabilitiesAdjusted : row.totalLiabilities),
  },
  {
    key: "equity", label: "PL (M)", group: "balanco",
    format: (row, mode) => millions(mode === "adjusted" ? row.stockholdersEquityAdjusted : row.stockholdersEquity),
  },
  {
    key: "debtToEquity", label: "Dív/PL", group: "balanco",
    format: (row) => ratio(row.debtToEquity),
  },
  {
    key: "liabToEquity", label: "Pass/PL", group: "balanco",
    format: (row) => ratio(row.liabilitiesToEquity),
  },
  {
    key: "currentRatio", label: "Liq. Corr.", group: "balanco",
    format: (row) => ratio(row.currentRatio),
  },
  // Resultado
  {
    key: "revenue", label: "Receita (M)", group: "resultado",
    format: (row, mode) => millions(mode === "adjusted" ? row.revenueAdjusted : row.revenue),
  },
  {
    key: "netIncome", label: "Lucro (M)", group: "resultado",
    format: (row, mode) => millionsWithSign(mode === "adjusted" ? row.netIncomeAdjusted : row.netIncome),
  },
  {
    key: "pe10", label: "P/L10", group: "resultado",
    format: (row) => ratio(row.pe10),
  },
  {
    key: "pe5", label: "P/L5", group: "resultado",
    format: (row) => ratio(row.pe5),
  },
  // Caixa
  {
    key: "fcf", label: "FCL (M)", group: "caixa",
    format: (row, mode) => millionsWithSign(mode === "adjusted" ? row.fcfAdjusted : row.fcf),
  },
  {
    key: "pfcl10", label: "P/FCL10", group: "caixa",
    format: (row) => ratio(row.pfcl10),
  },
  {
    key: "pfcl5", label: "P/FCL5", group: "caixa",
    format: (row) => ratio(row.pfcl5),
  },
  {
    key: "operatingCF", label: "FC Oper. (M)", group: "caixa",
    format: (row, mode) => millionsWithSign(mode === "adjusted" ? row.operatingCashFlowAdjusted : row.operatingCashFlow),
  },
  {
    key: "marketCap", label: "Market Cap (M)", group: "caixa",
    format: (row, mode) => millions(mode === "adjusted" ? row.marketCapAdjusted : row.marketCap),
  },
  {
    key: "dividends", label: "Dividendos (M)", group: "caixa",
    format: (row, mode) => {
      const value = mode === "adjusted" ? row.dividendsAdjusted : row.dividendsPaid;
      if (value === null) return null;
      // dividendsPaid is negative in BRAPI; show as positive
      return millions(Math.abs(value));
    },
  },
];

const BALANCE_COUNT = 6;
const RESULTADO_COUNT = 4;
const CAIXA_COUNT = 6;

const GROUP_START_INDICES = new Set([BALANCE_COUNT, BALANCE_COUNT + RESULTADO_COUNT]);

/* ── Component ── */

interface Props {
  ticker: string;
}

export function FundamentalsTab({ ticker }: Props) {
  const { data: rawData, isLoading, error } = useFundamentals(ticker, true);
  const [valueMode, setValueMode] = useState<ValueMode>("nominal");
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
        <div className="fundamentals-error">Sem dados fundamentais disponíveis.</div>
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
          Nominal
        </button>
        <button
          className={`fundamentals-toggle-pill ${valueMode === "adjusted" ? "fundamentals-toggle-pill-active" : ""}`}
          onClick={() => setValueMode(valueMode === "adjusted" ? "nominal" : "adjusted")}
        >
          IPCA
        </button>
      </div>

      <div className="fundamentals-scroll-wrapper">
        <table className="fundamentals-table">
          <thead>
            {/* Group header row */}
            <tr className="fundamentals-group-row">
              <th className="fundamentals-sticky-col" />
              <th colSpan={BALANCE_COUNT}>Balanço</th>
              <th colSpan={RESULTADO_COUNT} className="fundamentals-group-separator">Resultado</th>
              <th colSpan={CAIXA_COUNT} className="fundamentals-group-separator">Caixa</th>
            </tr>
            {/* Column header row */}
            <tr>
              <th className="fundamentals-sticky-col">Ano</th>
              {COLUMNS.map((col, index) => (
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
                {COLUMNS.map((col, index) => {
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
