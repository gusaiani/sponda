import { useState } from "react";
import "../styles/card.css";

interface QuarterlyDetail {
  end_date: string;
  net_income: number;
  eps: number;
}

interface YearlyBreakdown {
  year: number;
  nominalEPS: number;
  ipcaFactor: number;
  adjustedEPS: number;
  quarters: number;
  quarterlyDetail: QuarterlyDetail[];
}

interface PE10Data {
  ticker: string;
  name: string;
  pe10: number | null;
  currentPrice: number;
  marketCap: number | null;
  avgAdjustedEPS: number | null;
  yearsOfData: number;
  label: string;
  error: string | null;
  annualData: boolean;
  calculationDetails: YearlyBreakdown[];
}

interface PE10CardProps {
  data: PE10Data;
}

function formatCurrency(value: number): string {
  return value.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatLargeNumber(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 1e9) return `${(value / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `${(value / 1e6).toFixed(2)}M`;
  if (abs >= 1e3) return `${(value / 1e3).toFixed(1)}K`;
  return value.toFixed(0);
}

function formatQuarterLabel(dateStr: string): string {
  const [year, month] = dateStr.split("-").map(Number);
  const q = Math.ceil(month / 3);
  return `${q}T${year}`;
}

function CalculationDetails({ data }: { data: PE10Data }) {
  const [expandedYear, setExpandedYear] = useState<number | null>(null);

  if (!data.calculationDetails.length) return null;

  const totalAdjustedEPS = data.calculationDetails.reduce((sum, y) => sum + y.adjustedEPS, 0);

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
              <th>LPA Nominal</th>
              <th>Fator IPCA</th>
              <th>LPA Ajustado</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {data.calculationDetails.map((year) => (
              <>
                <tr key={year.year} className="pe10-calc-year-row">
                  <td>{year.year}</td>
                  <td>R$ {formatCurrency(year.nominalEPS)}</td>
                  <td>{year.ipcaFactor.toFixed(4)}×</td>
                  <td>R$ {formatCurrency(year.adjustedEPS)}</td>
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
                    <td colSpan={2}>
                      Lucro líquido: R$ {formatLargeNumber(q.net_income)}
                    </td>
                    <td colSpan={2}>LPA: R$ {q.eps.toFixed(4)}</td>
                  </tr>
                ))}
              </>
            ))}
          </tbody>
        </table>
      </div>

      {/* Step 2: Average */}
      <div className="pe10-calc-section">
        <div className="pe10-calc-section-title">2. LPA médio ajustado</div>
        <div className="pe10-calc-formula">
          <span>Soma dos LPA ajustados</span>
          <span className="pe10-calc-formula-val">R$ {formatCurrency(totalAdjustedEPS)}</span>
        </div>
        <div className="pe10-calc-formula">
          <span>÷ {data.yearsOfData} anos</span>
          <span className="pe10-calc-formula-val">
            = R$ {data.avgAdjustedEPS !== null ? formatCurrency(data.avgAdjustedEPS) : "N/A"}
          </span>
        </div>
      </div>

      {/* Step 3: Division */}
      {data.pe10 !== null && data.avgAdjustedEPS !== null && (
        <div className="pe10-calc-section">
          <div className="pe10-calc-section-title">3. {data.label}</div>
          <div className="pe10-calc-formula">
            <span>Preço atual</span>
            <span className="pe10-calc-formula-val">R$ {formatCurrency(data.currentPrice)}</span>
          </div>
          <div className="pe10-calc-formula">
            <span>÷ LPA médio ajustado</span>
            <span className="pe10-calc-formula-val">R$ {formatCurrency(data.avgAdjustedEPS)}</span>
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
          <div className="pe10-detail-label">LPA Médio Ajustado</div>
          <div className="pe10-detail-value">
            {data.avgAdjustedEPS !== null
              ? `R$ ${data.avgAdjustedEPS.toFixed(2)}`
              : "N/A"}
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
