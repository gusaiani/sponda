import "../styles/card.css";

interface PE10Data {
  ticker: string;
  name: string;
  pe10: number | null;
  currentPrice: number;
  avgAdjustedEPS: number | null;
  yearsOfData: number;
  label: string;
  error: string | null;
  annualData: boolean;
}

interface PE10CardProps {
  data: PE10Data;
}

export function PE10Card({ data }: PE10CardProps) {
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
