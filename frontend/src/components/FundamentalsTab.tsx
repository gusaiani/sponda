import { useState } from "react";
import { useFundamentals, type FundamentalsYear } from "../hooks/useFundamentals";
import { br } from "../utils/format";
import "../styles/fundamentals.css";

/* ── Column definitions ── */

type ValueMode = "nominal" | "adjusted";

interface ColumnDef {
  key: string;
  label: string;
  group: "balanco" | "resultado" | "caixa";
  format: (row: FundamentalsYear, mode: ValueMode) => string | null;
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
    format: (row) => millions(row.debtExLease),
  },
  {
    key: "totalLiabilities", label: "Passivo (M)", group: "balanco",
    format: (row) => millions(row.totalLiabilities),
  },
  {
    key: "equity", label: "PL (M)", group: "balanco",
    format: (row) => millions(row.stockholdersEquity),
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
  // Caixa
  {
    key: "fcf", label: "FCL (M)", group: "caixa",
    format: (row, mode) => millionsWithSign(mode === "adjusted" ? row.fcfAdjusted : row.fcf),
  },
  {
    key: "operatingCF", label: "FC Oper. (M)", group: "caixa",
    format: (row, mode) => millionsWithSign(mode === "adjusted" ? row.operatingCashFlowAdjusted : row.operatingCashFlow),
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
const RESULTADO_COUNT = 2;
const CAIXA_COUNT = 3;

/* ── Component ── */

interface Props {
  ticker: string;
}

export function FundamentalsTab({ ticker }: Props) {
  const { data, isLoading, error } = useFundamentals(ticker, true);
  const [valueMode, setValueMode] = useState<ValueMode>("nominal");

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
          onClick={() => setValueMode("nominal")}
        >
          Nominal
        </button>
        <button
          className={`fundamentals-toggle-pill ${valueMode === "adjusted" ? "fundamentals-toggle-pill-active" : ""}`}
          onClick={() => setValueMode("adjusted")}
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
              <th colSpan={RESULTADO_COUNT}>Resultado</th>
              <th colSpan={CAIXA_COUNT}>Caixa</th>
            </tr>
            {/* Column header row */}
            <tr>
              <th className="fundamentals-sticky-col">Ano</th>
              {COLUMNS.map((col) => (
                <th key={col.key}>{col.label}</th>
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
                {COLUMNS.map((col) => {
                  const formatted = col.format(row, valueMode);
                  if (formatted === null) {
                    return (
                      <td key={col.key}>
                        <span className="fundamentals-null">—</span>
                      </td>
                    );
                  }
                  const rawValue = getRawValue(row, col.key, valueMode);
                  const isNegative = rawValue !== null && rawValue < 0;
                  return (
                    <td key={col.key} className={isNegative ? "fundamentals-negative" : ""}>
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

function getRawValue(row: FundamentalsYear, key: string, mode: ValueMode): number | null {
  switch (key) {
    case "debtExLease": return row.debtExLease;
    case "totalLiabilities": return row.totalLiabilities;
    case "equity": return row.stockholdersEquity;
    case "debtToEquity": return row.debtToEquity;
    case "liabToEquity": return row.liabilitiesToEquity;
    case "currentRatio": return row.currentRatio;
    case "revenue": return mode === "adjusted" ? row.revenueAdjusted : row.revenue;
    case "netIncome": return mode === "adjusted" ? row.netIncomeAdjusted : row.netIncome;
    case "fcf": return mode === "adjusted" ? row.fcfAdjusted : row.fcf;
    case "operatingCF": return mode === "adjusted" ? row.operatingCashFlowAdjusted : row.operatingCashFlow;
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
