import { useState } from "react";
import "../styles/card.css";

interface QuarterlyDetail {
  end_date: string;
  net_income: number;
}

interface YearlyBreakdown {
  year: number;
  nominalNetIncome: number;
  ipcaFactor: number;
  adjustedNetIncome: number;
  quarters: number;
  quarterlyDetail: QuarterlyDetail[];
}

interface PE10Data {
  ticker: string;
  name: string;
  pe10: number | null;
  currentPrice: number;
  marketCap: number | null;
  avgAdjustedNetIncome: number | null;
  yearsOfData: number;
  label: string;
  error: string | null;
  annualData: boolean;
  calculationDetails: YearlyBreakdown[];
}

interface PE10CardProps {
  data: PE10Data;
}

function formatLargeNumber(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 1e9) return `R$ ${(value / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `R$ ${(value / 1e6).toFixed(2)}M`;
  if (abs >= 1e3) return `R$ ${(value / 1e3).toFixed(1)}K`;
  return `R$ ${value.toFixed(0)}`;
}

function formatQuarterLabel(dateStr: string): string {
  const [year, month] = dateStr.split("-").map(Number);
  const q = Math.ceil(month / 3);
  return `${q}T${year}`;
}

function CalculationDetails({ data }: { data: PE10Data }) {
  const [expandedYear, setExpandedYear] = useState<number | null>(null);

  if (!data.calculationDetails.length) return null;

  const totalAdjusted = data.calculationDetails.reduce((sum, y) => sum + y.adjustedNetIncome, 0);

  return (
    <div className="pe10-calc-details">
      <h4 className="pe10-calc-title">Memória de Cálculo</h4>

      {/* Step 1: Yearly earnings table */}
      <div className="pe10-calc-section">
        <div className="pe10-calc-section-title">1. Lucros anuais e ajuste por inflação (IPCA)</div>
        <table className="pe10-calc-table">
          <thead>
            <tr>
              <th>Ano</th>
              <th>Lucro Líquido</th>
              <th>Fator IPCA</th>
              <th>Lucro Ajustado</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {data.calculationDetails.map((year) => (
              <>
                <tr key={year.year} className="pe10-calc-year-row">
                  <td>{year.year}</td>
                  <td>{formatLargeNumber(year.nominalNetIncome)}</td>
                  <td>{year.ipcaFactor.toFixed(4)}×</td>
                  <td>{formatLargeNumber(year.adjustedNetIncome)}</td>
                  <td>
                    <button
                      className="pe10-calc-expand-btn"
                      onClick={() => setExpandedYear(expandedYear === year.year ? null : year.year)}
                      aria-label={expandedYear === year.year ? "Recolher trimestres" : "Expandir trimestres"}
                    >
                      <span className={`pe10-explainer-chevron ${expandedYear === year.year ? "pe10-explainer-chevron-open" : ""}`}>
                        ▼
                      </span>
                    </button>
                  </td>
                </tr>
                {expandedYear === year.year && year.quarterlyDetail.map((q) => (
                  <tr key={q.end_date} className="pe10-calc-quarter-row">
                    <td className="pe10-calc-quarter-label">{formatQuarterLabel(q.end_date)}</td>
                    <td colSpan={4}>
                      Lucro líquido: {formatLargeNumber(q.net_income)}
                    </td>
                  </tr>
                ))}
              </>
            ))}
          </tbody>
        </table>
      </div>

      {/* Step 2: Average */}
      <div className="pe10-calc-section">
        <div className="pe10-calc-section-title">2. Lucro líquido médio ajustado</div>
        <div className="pe10-calc-formula">
          <span>Soma dos lucros ajustados</span>
          <span className="pe10-calc-formula-val">{formatLargeNumber(totalAdjusted)}</span>
        </div>
        <div className="pe10-calc-formula">
          <span>÷ {data.yearsOfData} anos</span>
          <span className="pe10-calc-formula-val">
            = {data.avgAdjustedNetIncome !== null ? formatLargeNumber(data.avgAdjustedNetIncome) : "N/A"}
          </span>
        </div>
      </div>

      {/* Step 3: Division */}
      {data.pe10 !== null && data.avgAdjustedNetIncome !== null && data.marketCap !== null && (
        <div className="pe10-calc-section">
          <div className="pe10-calc-section-title">3. {data.label}</div>
          <div className="pe10-calc-formula">
            <span>Market Cap</span>
            <span className="pe10-calc-formula-val">{formatLargeNumber(data.marketCap)}</span>
          </div>
          <div className="pe10-calc-formula">
            <span>÷ Lucro líquido médio ajustado</span>
            <span className="pe10-calc-formula-val">{formatLargeNumber(data.avgAdjustedNetIncome)}</span>
          </div>
          <div className="pe10-calc-formula pe10-calc-result">
            <span>= {data.label}</span>
            <span className="pe10-calc-formula-val">{data.pe10.toFixed(2)}</span>
          </div>
        </div>
      )}
    </div>
  );
}

export function PE10Card({ data }: PE10CardProps) {
  const [showDetails, setShowDetails] = useState(false);

  return (
    <div className="pe10-card">
      <div className="pe10-card-header">
        <span className="pe10-ticker">{data.ticker}</span>
        <span className="pe10-name">{data.name}</span>
      </div>

      <div className="pe10-value-container">
        <div className="pe10-label">{data.label}</div>
        {data.pe10 !== null ? (
          <div className="pe10-value">{data.pe10.toFixed(1)}</div>
        ) : (
          <div className="pe10-error">{data.error}</div>
        )}
      </div>

      {data.annualData && (
        <div className="pe10-warning">
          Atenção: usando demonstrações de resultado anuais. Dados trimestrais
          indisponíveis para este ticker.
        </div>
      )}

      <div className="pe10-details">
        <div className="pe10-detail-item">
          <div className="pe10-detail-label">Preço Atual</div>
          <div className="pe10-detail-value">
            R$ {data.currentPrice.toFixed(2)}
          </div>
        </div>
        <div className="pe10-detail-item">
          <div className="pe10-detail-label">Market Cap</div>
          <div className="pe10-detail-value">
            {data.marketCap !== null ? formatLargeNumber(data.marketCap) : "N/A"}
          </div>
        </div>
        <div className="pe10-detail-item">
          <div className="pe10-detail-label">Anos de Dados</div>
          <div className="pe10-detail-value">{data.yearsOfData}</div>
        </div>
      </div>

      {data.calculationDetails.length > 0 && (
        <div className="pe10-calc-wrapper">
          <button
            className="pe10-calc-toggle"
            onClick={() => setShowDetails(!showDetails)}
          >
            Memória de cálculo
            <span className={`pe10-explainer-chevron ${showDetails ? "pe10-explainer-chevron-open" : ""}`}>
              ▼
            </span>
          </button>
          {showDetails && <CalculationDetails data={data} />}
        </div>
      )}
    </div>
  );
}

export function PE10CardLoading() {
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
