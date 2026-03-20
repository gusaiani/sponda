import { useCompareData, type CompareEntry } from "../hooks/useCompareData";
import { CompanySearchInput } from "./CompanySearchInput";
import { br } from "../utils/format";
import type { QuoteResult } from "../hooks/usePE10";
import "../styles/compare.css";

/* ── Column definitions ── */

interface ColumnDef {
  key: string;
  label: string;
  group: "endividamento" | "rentabilidade" | "valuation";
  format: (d: QuoteResult) => string | null;
}

function getColumns(years: number): ColumnDef[] {
  const n = years;
  return [
    // Endividamento
    { key: "debtToEquity", label: "Dív/PL", group: "endividamento", format: (d) => d.debtToEquity !== null ? br(d.debtToEquity, 2) : null },
    { key: "debtExLeaseToEquity", label: "Dív-Arr/PL", group: "endividamento", format: (d) => d.debtExLeaseToEquity !== null ? br(d.debtExLeaseToEquity, 2) : null },
    { key: "liabilitiesToEquity", label: "Pass/PL", group: "endividamento", format: (d) => d.liabilitiesToEquity !== null ? br(d.liabilitiesToEquity, 2) : null },
    { key: "debtToAvgEarnings", label: `Dív/Lucro${n}`, group: "endividamento", format: (d) => d.debtToAvgEarnings !== null ? br(d.debtToAvgEarnings, 1) : null },
    { key: "debtToAvgFCF", label: `Dív/FCL${n}`, group: "endividamento", format: (d) => d.debtToAvgFCF !== null ? br(d.debtToAvgFCF, 1) : null },
    // Rentabilidade
    { key: "roe", label: `ROE${n}`, group: "rentabilidade", format: (d) => d.roe !== null ? `${br(d.roe, 1)}%` : null },
    { key: "priceToBook", label: "P/VPA", group: "rentabilidade", format: (d) => d.priceToBook !== null ? br(d.priceToBook, 2) : null },
    // Valuation
    { key: "pe10", label: `P/L${n}`, group: "valuation", format: (d) => d.pe10 !== null ? br(d.pe10, 1) : null },
    { key: "pfcf10", label: `P/FCL${n}`, group: "valuation", format: (d) => d.pfcf10 !== null ? br(d.pfcf10, 1) : null },
    { key: "peg", label: `PEG${n}`, group: "valuation", format: (d) => d.peg !== null ? br(d.peg, 2) : null },
    { key: "pfcfPeg", label: `PFCLG${n}`, group: "valuation", format: (d) => d.pfcfPeg !== null ? br(d.pfcfPeg, 2) : null },
    { key: "earningsCAGR", label: `CAGR L${n}`, group: "valuation", format: (d) => d.earningsCAGR !== null ? `${br(d.earningsCAGR, 1)}%` : null },
    { key: "fcfCAGR", label: `CAGR FCL${n}`, group: "valuation", format: (d) => d.fcfCAGR !== null ? `${br(d.fcfCAGR, 1)}%` : null },
  ];
}

const DEBT_COUNT = 5;
const RENT_COUNT = 2;
const VAL_COUNT = 6;

/* ── Component ── */

interface Props {
  currentTicker: string;
  years: number;
  maxYears: number;
  onYearsChange: (y: number) => void;
  extraTickers: string[];
  onExtraTickersChange: (tickers: string[]) => void;
}

export function CompareTab({ currentTicker, years, maxYears, onYearsChange, extraTickers, onExtraTickersChange }: Props) {
  const allTickers = [currentTicker, ...extraTickers];
  const entries = useCompareData(allTickers, years);
  const columns = getColumns(years);

  function handleAdd(ticker: string) {
    const upper = ticker.toUpperCase();
    if (!allTickers.includes(upper)) {
      onExtraTickersChange([...extraTickers, upper]);
    }
  }

  function handleRemove(ticker: string) {
    onExtraTickersChange(extraTickers.filter((t) => t !== ticker));
  }

  return (
    <div className="compare-container">
      {/* Scrollable table */}
      <div className="compare-scroll-wrapper">
        <table className="compare-table">
          <thead>
            {/* Group header */}
            <tr className="compare-group-row">
              <th className="compare-sticky-col" />
              <th colSpan={DEBT_COUNT}>Endividamento</th>
              <th colSpan={RENT_COUNT}>Rentabilidade</th>
              <th colSpan={VAL_COUNT}>Preço vs. Resultados</th>
              <th />
            </tr>
            {/* Column headers */}
            <tr>
              <th className="compare-sticky-col">Empresa</th>
              {columns.map((col) => (
                <th key={col.key}>{col.label}</th>
              ))}
              <th />
            </tr>
          </thead>
          <tbody>
            {entries.map((entry, i) => (
              <CompareRow
                key={entry.ticker}
                entry={entry}
                isCurrentTicker={i === 0}
                onRemove={handleRemove}
                columns={columns}
              />
            ))}
            {/* Add company row */}
            <tr className="compare-add-row">
              <td className="compare-sticky-col">
                <CompanySearchInput
                  onAdd={handleAdd}
                  excludeTickers={allTickers}
                />
              </td>
              <td colSpan={columns.length + 1} />
            </tr>
          </tbody>
        </table>
      </div>

      {/* Years slider — below table */}
      <div className="compare-slider-wrapper">
        <div className="years-slider">
          <div className="years-slider-track">
            <span className="years-slider-bound">1</span>
            <input
              type="range"
              className="years-slider-input"
              min={1}
              max={maxYears}
              value={years}
              onChange={(e) => onYearsChange(Number(e.target.value))}
            />
            <span className="years-slider-bound">{maxYears}</span>
          </div>
          <p className="years-slider-caption">
            Analisando os últimos <strong>{years} {years === 1 ? "ano" : "anos"}</strong>
          </p>
        </div>
      </div>
    </div>
  );
}

/* ── Row component ── */

function CompareRow({
  entry,
  isCurrentTicker,
  onRemove,
  columns,
}: {
  entry: CompareEntry;
  isCurrentTicker: boolean;
  onRemove: (ticker: string) => void;
  columns: ColumnDef[];
}) {
  const { ticker, data, isLoading, error } = entry;

  if (isLoading) {
    return (
      <tr>
        <td className="compare-sticky-col">
          <div className="compare-company-cell">
            <span className="compare-company-ticker">{ticker}</span>
          </div>
        </td>
        {columns.map((col) => (
          <td key={col.key}>
            <div className="compare-loading-cell" />
          </td>
        ))}
        <td />
      </tr>
    );
  }

  if (error || !data) {
    return (
      <tr>
        <td className="compare-sticky-col">
          <div className="compare-company-cell">
            <span className="compare-company-ticker">{ticker}</span>
          </div>
        </td>
        <td colSpan={columns.length}>
          <span className="compare-error-cell">
            {error?.message ?? "Dados indisponíveis"}
          </span>
        </td>
        <td>
          {!isCurrentTicker && (
            <button className="compare-remove-btn" onClick={() => onRemove(ticker)} aria-label={`Remover ${ticker}`}>
              ×
            </button>
          )}
        </td>
      </tr>
    );
  }

  return (
    <tr>
      <td className="compare-sticky-col">
        <div className="compare-company-cell">
          {data.logo && (
            <img
              className="compare-company-logo"
              src={data.logo}
              alt=""
              onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
            />
          )}
          <span className="compare-company-name">{data.name}</span>
          <span className="compare-company-ticker">{ticker}</span>
        </div>
      </td>
      {columns.map((col) => {
        const formatted = col.format(data);
        return (
          <td key={col.key}>
            {formatted !== null ? formatted : <span className="compare-null">—</span>}
          </td>
        );
      })}
      <td>
        {!isCurrentTicker && (
          <button className="compare-remove-btn" onClick={() => onRemove(ticker)} aria-label={`Remover ${ticker}`}>
            ×
          </button>
        )}
      </td>
    </tr>
  );
}
