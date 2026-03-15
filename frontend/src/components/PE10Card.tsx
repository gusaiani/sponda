import { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import "../styles/card.css";

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
  // Leverage
  debtToEquity: number | null;
  liabilitiesToEquity: number | null;
  leverageError: string | null;
  leverageDate: string | null;
  totalDebt: number | null;
  totalLiabilities: number | null;
  stockholdersEquity: number | null;
}

interface PE10CardProps {
  data: QuoteData;
}

/** Map backend labels (PE10, PFCF7…) to Portuguese equivalents */
function ptLabel(label: string): string {
  return label.replace(/^PE/, "P/L").replace(/^PFCF/, "P/FCL");
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

/* ── P/L10 "Entenda melhor" ── */

function PL10Details({ data }: { data: QuoteData }) {
  const [expandedYear, setExpandedYear] = useState<number | null>(null);
  const label = ptLabel(data.pe10Label);
  const hasCalc = data.pe10CalculationDetails.length > 0;
  const total = hasCalc
    ? data.pe10CalculationDetails.reduce((s, y) => s + y.adjustedNetIncome, 0)
    : 0;

  return (
    <>
      <div className="modal-explainer">
        <p>
          O <strong>{label}</strong> (também conhecido como <strong>CAPE</strong>)
          é o índice preço/lucro calculado sobre a média dos lucros reais
          (ajustados pela inflação) dos últimos 10 anos.
        </p>
        <p>
          Ao suavizar oscilações cíclicas de curto prazo, o {label} oferece uma
          visão mais estável de quanto o mercado está pagando por cada real de
          lucro. Valores elevados sugerem que o ativo pode estar caro em
          relação ao seu histórico de rentabilidade, enquanto valores baixos
          podem indicar oportunidades.
        </p>
        <p>
          <strong>Atenção:</strong> para empresas em forte crescimento ou
          declínio, o {label} pode levar a conclusões equivocadas, já que a média
          de 10 anos não reflete a trajetória recente dos lucros. Use-o como
          um dos fatores da análise, não como critério único.
        </p>
      </div>

      {hasCalc && (
        <div className="pe10-calc-details">
          <h4 className="pe10-calc-title">Como é feito o cálculo</h4>

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
                {data.pe10CalculationDetails.map((year) => (
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
                        >
                          <span className={`pe10-explainer-chevron ${expandedYear === year.year ? "pe10-explainer-chevron-open" : ""}`}>▼</span>
                        </button>
                      </td>
                    </tr>
                    {expandedYear === year.year && year.quarterlyDetail.map((q) => (
                      <tr key={q.end_date} className="pe10-calc-quarter-row">
                        <td className="pe10-calc-quarter-label">{formatQuarterLabel(q.end_date)}</td>
                        <td colSpan={4}>Lucro líquido: {formatLargeNumber(q.net_income)}</td>
                      </tr>
                    ))}
                  </>
                ))}
              </tbody>
            </table>
          </div>

          <div className="pe10-calc-section">
            <div className="pe10-calc-section-title">2. Lucro líquido médio ajustado</div>
            <div className="pe10-calc-formula">
              <span>Soma dos lucros ajustados</span>
              <span className="pe10-calc-formula-val">{formatLargeNumber(total)}</span>
            </div>
            <div className="pe10-calc-formula">
              <span>÷ {data.pe10YearsOfData} anos</span>
              <span className="pe10-calc-formula-val">
                = {data.avgAdjustedNetIncome !== null ? formatLargeNumber(data.avgAdjustedNetIncome) : "N/A"}
              </span>
            </div>
          </div>

          {data.pe10 !== null && data.avgAdjustedNetIncome !== null && data.marketCap !== null && (
            <div className="pe10-calc-section">
              <div className="pe10-calc-section-title">3. {label}</div>
              <div className="pe10-calc-formula">
                <span>Market Cap</span>
                <span className="pe10-calc-formula-val">{formatLargeNumber(data.marketCap)}</span>
              </div>
              <div className="pe10-calc-formula">
                <span>÷ Lucro líquido médio ajustado</span>
                <span className="pe10-calc-formula-val">{formatLargeNumber(data.avgAdjustedNetIncome)}</span>
              </div>
              <div className="pe10-calc-formula pe10-calc-result">
                <span>= {label}</span>
                <span className="pe10-calc-formula-val">{data.pe10.toFixed(2)}</span>
              </div>
            </div>
          )}
        </div>
      )}
    </>
  );
}

/* ── P/FCL10 "Entenda melhor" ── */

function PFCL10Details({ data }: { data: QuoteData }) {
  const [expandedYear, setExpandedYear] = useState<number | null>(null);
  const label = ptLabel(data.pfcf10Label);
  const hasCalc = data.pfcf10CalculationDetails.length > 0;
  const total = hasCalc
    ? data.pfcf10CalculationDetails.reduce((s, y) => s + y.adjustedFCF, 0)
    : 0;

  return (
    <>
      <div className="modal-explainer">
        <p>
          O <strong>{label}</strong> é o índice preço/fluxo de caixa livre
          calculado sobre a média do fluxo de caixa livre real (ajustado pela
          inflação) dos últimos 10 anos.
        </p>
        <p>
          <strong>Fluxo de caixa livre (FCL)</strong> é o caixa que a empresa
          de fato gera após seus investimentos. Aqui, definimos FCL como
          fluxo de caixa operacional + fluxo de caixa de investimento.
        </p>
        <p>
          <strong>Qual a diferença entre FCL e lucro?</strong> O lucro líquido
          é um número contábil que inclui itens não-monetários como depreciação,
          amortização e provisões. Uma empresa pode reportar lucro alto mas gerar
          pouco caixa — ou vice-versa. O FCL mostra quanto dinheiro realmente
          entrou (ou saiu) do caixa, o que é mais difícil de manipular e mais
          relevante para quem quer saber o que a empresa pode distribuir aos
          acionistas ou reinvestir.
        </p>
        <p>
          O {label} complementa o {ptLabel(data.pe10Label)}: comparar os dois
          indicadores para uma mesma empresa revela se os lucros reportados se
          traduzem em geração real de caixa.
        </p>
      </div>

      {hasCalc && (
        <div className="pe10-calc-details">
          <h4 className="pe10-calc-title">Como é feito o cálculo</h4>

          <div className="pe10-calc-section">
            <div className="pe10-calc-section-title">1. FCL anual e ajuste por inflação (IPCA)</div>
            <table className="pe10-calc-table">
              <thead>
                <tr>
                  <th>Ano</th>
                  <th>FCL Nominal</th>
                  <th>Fator IPCA</th>
                  <th>FCL Ajustado</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {data.pfcf10CalculationDetails.map((year) => (
                  <>
                    <tr key={year.year} className="pe10-calc-year-row">
                      <td>{year.year}</td>
                      <td>{formatLargeNumber(year.nominalFCF)}</td>
                      <td>{year.ipcaFactor.toFixed(4)}×</td>
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
                          Operacional: {formatLargeNumber(q.operating_cash_flow)}
                          {" · "}
                          Investimento: {formatLargeNumber(q.investment_cash_flow)}
                        </td>
                      </tr>
                    ))}
                  </>
                ))}
              </tbody>
            </table>
          </div>

          <div className="pe10-calc-section">
            <div className="pe10-calc-section-title">2. FCL médio ajustado</div>
            <div className="pe10-calc-formula">
              <span>Soma dos FCL ajustados</span>
              <span className="pe10-calc-formula-val">{formatLargeNumber(total)}</span>
            </div>
            <div className="pe10-calc-formula">
              <span>÷ {data.pfcf10YearsOfData} anos</span>
              <span className="pe10-calc-formula-val">
                = {data.avgAdjustedFCF !== null ? formatLargeNumber(data.avgAdjustedFCF) : "N/A"}
              </span>
            </div>
          </div>

          {data.pfcf10 !== null && data.avgAdjustedFCF !== null && data.marketCap !== null && (
            <div className="pe10-calc-section">
              <div className="pe10-calc-section-title">3. {label}</div>
              <div className="pe10-calc-formula">
                <span>Market Cap</span>
                <span className="pe10-calc-formula-val">{formatLargeNumber(data.marketCap)}</span>
              </div>
              <div className="pe10-calc-formula">
                <span>÷ FCL médio ajustado</span>
                <span className="pe10-calc-formula-val">{formatLargeNumber(data.avgAdjustedFCF)}</span>
              </div>
              <div className="pe10-calc-formula pe10-calc-result">
                <span>= {label}</span>
                <span className="pe10-calc-formula-val">{data.pfcf10.toFixed(2)}</span>
              </div>
            </div>
          )}
        </div>
      )}
    </>
  );
}

/* ── Leverage "Entenda melhor" ── */

function LeverageDetails({ data }: { data: QuoteData }) {
  return (
    <>
      <div className="modal-explainer">
        <p>
          <strong>Dívida Bruta / PL</strong> mede quanto da estrutura de capital
          da empresa é financiada por dívida em relação ao patrimônio dos
          acionistas. Valores altos indicam maior alavancagem financeira e,
          portanto, maior risco em cenários adversos.
        </p>
        <p>
          <strong>Passivo / PL</strong> é uma medida mais ampla: considera todas
          as obrigações da empresa (não apenas dívidas financeiras, mas também
          fornecedores, tributos, provisões etc.) em relação ao patrimônio
          líquido. Valores elevados sugerem que a empresa depende mais de
          capital de terceiros do que de capital próprio.
        </p>
        <p>
          <strong>Atenção:</strong> estes indicadores devem ser comparados entre
          empresas do mesmo setor. Setores como infraestrutura e bancos operam
          naturalmente com alavancagem mais elevada.
        </p>
      </div>

      {data.stockholdersEquity !== null && (
        <div className="pe10-calc-details">
          <h4 className="pe10-calc-title">Valores do balanço</h4>
          {data.leverageDate && (
            <div className="pe10-calc-section">
              <div className="pe10-calc-section-title">Data do balanço</div>
              <div className="pe10-calc-formula">
                <span>Referência</span>
                <span className="pe10-calc-formula-val">{data.leverageDate}</span>
              </div>
            </div>
          )}

          <div className="pe10-calc-section">
            <div className="pe10-calc-section-title">Componentes</div>
            {data.totalDebt !== null && (
              <div className="pe10-calc-formula">
                <span>Dívida Bruta</span>
                <span className="pe10-calc-formula-val">{formatLargeNumber(data.totalDebt)}</span>
              </div>
            )}
            {data.totalLiabilities !== null && (
              <div className="pe10-calc-formula">
                <span>Passivo Total</span>
                <span className="pe10-calc-formula-val">{formatLargeNumber(data.totalLiabilities)}</span>
              </div>
            )}
            <div className="pe10-calc-formula">
              <span>Patrimônio Líquido</span>
              <span className="pe10-calc-formula-val">{formatLargeNumber(data.stockholdersEquity)}</span>
            </div>
          </div>

          {data.debtToEquity !== null && (
            <div className="pe10-calc-section">
              <div className="pe10-calc-section-title">Dívida Bruta / PL</div>
              <div className="pe10-calc-formula">
                <span>{formatLargeNumber(data.totalDebt!)} ÷ {formatLargeNumber(data.stockholdersEquity)}</span>
                <span className="pe10-calc-formula-val">= {data.debtToEquity.toFixed(2)}</span>
              </div>
            </div>
          )}

          {data.liabilitiesToEquity !== null && (
            <div className="pe10-calc-section">
              <div className="pe10-calc-section-title">Passivo / PL</div>
              <div className="pe10-calc-formula">
                <span>{formatLargeNumber(data.totalLiabilities!)} ÷ {formatLargeNumber(data.stockholdersEquity)}</span>
                <span className="pe10-calc-formula-val">= {data.liabilitiesToEquity.toFixed(2)}</span>
              </div>
            </div>
          )}
        </div>
      )}
    </>
  );
}

/* ── Main Card ── */

export function PE10Card({ data }: PE10CardProps) {
  const [showPL10, setShowPL10] = useState(false);
  const [showPFCL10, setShowPFCL10] = useState(false);
  const [showLeverage, setShowLeverage] = useState(false);

  const pl10Label = ptLabel(data.pe10Label);
  const pfcl10Label = ptLabel(data.pfcf10Label);

  const hasLeverage = data.debtToEquity !== null || data.liabilitiesToEquity !== null;

  return (
    <div className="pe10-card">
      <div className="pe10-card-header">
        <span className="pe10-name">{data.name}</span>
        <span className="pe10-ticker">{data.ticker}</span>
      </div>

      {/* Two metrics side by side */}
      <div className="metrics-row">
        {/* P/L10 */}
        <div className="metric-block">
          <div className="metric-value-container">
            <div className="pe10-label">{pl10Label}</div>
            {data.pe10 !== null ? (
              <div className="pe10-value">{data.pe10.toFixed(1)}</div>
            ) : (
              <div className="pe10-error">{data.pe10Error}</div>
            )}
          </div>
          <button
            className="metric-toggle"
            onClick={() => setShowPL10(true)}
          >
            <svg className="metric-toggle-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8S1 12 1 12z"/><circle cx="12" cy="12" r="3"/></svg>
            Entenda melhor
          </button>
          {showPL10 && (
            <Modal title={`${pl10Label} — ${data.name}`} onClose={() => setShowPL10(false)}>
              <PL10Details data={data} />
            </Modal>
          )}
        </div>

        {/* P/FCL10 */}
        <div className="metric-block">
          <div className="metric-value-container">
            <div className="pe10-label">{pfcl10Label}</div>
            {data.pfcf10 !== null ? (
              <div className="pe10-value">{data.pfcf10.toFixed(1)}</div>
            ) : (
              <div className="pe10-error">{data.pfcf10Error}</div>
            )}
          </div>
          <button
            className="metric-toggle"
            onClick={() => setShowPFCL10(true)}
          >
            <svg className="metric-toggle-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8S1 12 1 12z"/><circle cx="12" cy="12" r="3"/></svg>
            Entenda melhor
          </button>
          {showPFCL10 && (
            <Modal title={`${pfcl10Label} — ${data.name}`} onClose={() => setShowPFCL10(false)}>
              <PFCL10Details data={data} />
            </Modal>
          )}
        </div>
      </div>

      {/* Leverage metrics */}
      <div className="metrics-row leverage-row">
        <div className="metric-block">
          <div className="metric-value-container">
            <div className="pe10-label">Dív. Bruta / PL</div>
            {data.debtToEquity !== null ? (
              <div className="pe10-value">{data.debtToEquity.toFixed(2)}</div>
            ) : (
              <div className="pe10-error">{data.leverageError || "N/A"}</div>
            )}
          </div>
        </div>
        <div className="metric-block">
          <div className="metric-value-container">
            <div className="pe10-label">Passivo / PL</div>
            {data.liabilitiesToEquity !== null ? (
              <div className="pe10-value">{data.liabilitiesToEquity.toFixed(2)}</div>
            ) : (
              <div className="pe10-error">{data.leverageError || "N/A"}</div>
            )}
          </div>
        </div>
      </div>
      {hasLeverage && (
        <button
          className="metric-toggle leverage-toggle"
          onClick={() => setShowLeverage(true)}
        >
          <svg className="metric-toggle-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8S1 12 1 12z"/><circle cx="12" cy="12" r="3"/></svg>
          Entenda melhor
        </button>
      )}
      {showLeverage && (
        <Modal title={`Alavancagem — ${data.name}`} onClose={() => setShowLeverage(false)}>
          <LeverageDetails data={data} />
        </Modal>
      )}

      {(data.pe10AnnualData || data.pfcf10AnnualData) && (
        <div className="pe10-warning">
          Atenção: usando demonstrações anuais. Dados trimestrais
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
          <div className="pe10-detail-value">
            {data.pe10YearsOfData === data.pfcf10YearsOfData
              ? data.pe10YearsOfData
              : `${data.pe10YearsOfData} / ${data.pfcf10YearsOfData}`}
          </div>
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
