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

interface PE10CardProps {
  data: QuoteData;
  years: number;
  maxYears: number;
  onYearsChange: (years: number) => void;
}

type ModalKey =
  | "debtToEquity" | "debtExLease" | "liabToEquity"
  | "debtToEarnings" | "debtToFCF"
  | "pl10" | "peg" | "cagrEarnings"
  | "pfcl10" | "pfclg" | "cagrFCF"
  | null;

import { ptLabel, br, formatLargeNumber, formatQuarterLabel } from "../utils/format";

/* ── Inline ? button ── */

function InfoBtn({ onClick }: { onClick: () => void }) {
  return (
    <button className="info-btn" onClick={onClick} type="button" aria-label="Mais informações">
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
  if (data.stockholdersEquity === null) return null;
  return (
    <div className="pe10-calc-details">
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
        {data.totalLease !== null && (
          <div className="pe10-calc-formula">
            <span>Arrendamentos (Leasing)</span>
            <span className="pe10-calc-formula-val">{formatLargeNumber(data.totalLease)}</span>
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
    </div>
  );
}

/* ── Per-metric modal content ── */

function DebtToEquityInfo({ data }: { data: QuoteData }) {
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
          Compare entre empresas do mesmo setor. Setores como infraestrutura e
          bancos operam naturalmente com alavancagem mais elevada.
        </p>
      </div>
      <BalanceSheetComponents data={data} />
      {data.debtToEquity !== null && data.stockholdersEquity !== null && (
        <div className="pe10-calc-details">
          <div className="pe10-calc-section">
            <div className="pe10-calc-section-title">Cálculo</div>
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
  return (
    <>
      <div className="modal-explainer">
        <p>
          <strong>Dív - Arrend. / PL</strong> é a dívida bruta excluindo
          arrendamentos (leasing) dividida pelo patrimônio líquido. Com a adoção
          do IFRS 16, obrigações de leasing passaram a ser registradas como
          dívida no balanço. Excluí-las mostra a alavancagem financeira "pura",
          sem o componente operacional de arrendamentos.
        </p>
      </div>
      <BalanceSheetComponents data={data} />
      {data.debtExLeaseToEquity !== null && data.totalDebt !== null && data.stockholdersEquity !== null && (
        <div className="pe10-calc-details">
          <div className="pe10-calc-section">
            <div className="pe10-calc-section-title">Cálculo</div>
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
  return (
    <>
      <div className="modal-explainer">
        <p>
          <strong>Passivo / PL</strong> considera todas as obrigações da empresa
          (não apenas dívidas financeiras, mas também fornecedores, tributos,
          provisões etc.) em relação ao patrimônio líquido. Valores elevados
          sugerem dependência de capital de terceiros.
        </p>
        <p>
          É uma medida mais ampla que Dív. Bruta / PL. Compare sempre entre
          empresas do mesmo setor.
        </p>
      </div>
      <BalanceSheetComponents data={data} />
      {data.liabilitiesToEquity !== null && data.stockholdersEquity !== null && (
        <div className="pe10-calc-details">
          <div className="pe10-calc-section">
            <div className="pe10-calc-section-title">Cálculo</div>
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
  return (
    <>
      <div className="modal-explainer">
        <p>
          <strong>Dív. Bruta / Lucro Médio</strong> indica quantos anos de lucro
          líquido médio (ajustado pela inflação, últimos 10 anos) seriam
          necessários para quitar a dívida bruta. Quanto menor, mais confortável.
        </p>
        <p>
          A média de 10 anos suaviza ciclos econômicos e resultados atípicos.
          N/A indica lucro médio negativo no período.
        </p>
      </div>
      {data.totalDebt !== null && data.debtToAvgEarnings !== null && data.avgAdjustedNetIncome !== null && (
        <div className="pe10-calc-details">
          <div className="pe10-calc-section">
            <div className="pe10-calc-section-title">Cálculo</div>
            <div className="pe10-calc-formula">
              <span>Dívida Bruta</span>
              <span className="pe10-calc-formula-val">{formatLargeNumber(data.totalDebt)}</span>
            </div>
            <div className="pe10-calc-formula">
              <span>Lucro Líquido Médio Ajustado ({data.pe10YearsOfData}a)</span>
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
  return (
    <>
      <div className="modal-explainer">
        <p>
          <strong>Dív. Bruta / FCL Médio</strong> indica quantos anos de fluxo de
          caixa livre médio (ajustado pela inflação, últimos 10 anos) seriam
          necessários para quitar a dívida bruta. Como o FCL representa dinheiro
          que de fato entra no caixa, tende a ser mais conservador que o
          indicador baseado em lucro.
        </p>
      </div>
      {data.totalDebt !== null && data.debtToAvgFCF !== null && data.avgAdjustedFCF !== null && (
        <div className="pe10-calc-details">
          <div className="pe10-calc-section">
            <div className="pe10-calc-section-title">Cálculo</div>
            <div className="pe10-calc-formula">
              <span>Dívida Bruta</span>
              <span className="pe10-calc-formula-val">{formatLargeNumber(data.totalDebt)}</span>
            </div>
            <div className="pe10-calc-formula">
              <span>FCL Médio Ajustado ({data.pfcf10YearsOfData}a)</span>
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
          O <strong>{label}</strong> (CAPE) é o preço/lucro calculado sobre a
          média dos lucros reais (ajustados pela inflação) dos últimos 10 anos.
          Suaviza oscilações cíclicas e mostra quanto o mercado paga por real de
          lucro de forma mais estável.
        </p>
        <p>
          Valores elevados sugerem ativo caro; valores baixos podem indicar
          oportunidades. Para empresas em forte crescimento ou declínio, a média
          de 10 anos pode não refletir a trajetória recente.
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
          O <strong>{label}</strong> é o preço/fluxo de caixa livre calculado
          sobre a média do FCL real (ajustado pela inflação) dos últimos 10 anos.
          FCL = fluxo de caixa operacional + fluxo de caixa de investimento.
        </p>
        <p>
          Diferente do lucro contábil, o FCL mostra quanto dinheiro realmente
          entrou no caixa — mais difícil de manipular. Compare o {label} com
          o {ptLabel(data.pe10Label)} para ver se lucros se traduzem em caixa.
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
  const isEarnings = variant === "earnings";
  const label = isEarnings ? "PEG" : "PFCLG";
  const baseLabel = isEarnings ? ptLabel(data.pe10Label) : ptLabel(data.pfcf10Label);
  const baseValue = isEarnings ? data.pe10 : data.pfcf10;
  const cagr = isEarnings ? data.earningsCAGR : data.fcfCAGR;
  const peg = isEarnings ? data.peg : data.pfcfPeg;
  const method = isEarnings ? data.earningsCAGRMethod : data.fcfCAGRMethod;
  const excludedYears = isEarnings ? data.earningsCAGRExcludedYears : data.fcfCAGRExcludedYears;
  const metricName = isEarnings ? "lucros" : "fluxo de caixa livre";

  return (
    <>
      <div className="modal-explainer">
        <p>
          O <strong>{label}</strong>, popularizado por Peter Lynch, relaciona o
          múltiplo de {metricName} com o crescimento real da empresa:
          {" "}<strong>{baseLabel}</strong> ÷ <strong>CAGR</strong> {isEarnings ? "dos lucros reais" : "do FCL real"}.
        </p>
        <p>
          Abaixo de 1 sugere preço atrativo em relação ao crescimento. Acima de
          1, o mercado pode estar pagando caro. Só é calculável quando o {baseLabel} é
          positivo e houve crescimento no período.
        </p>
        {!isEarnings && (
          <p>
            O PFCLG complementa o PEG: usa fluxo de caixa livre em vez de lucro
            contábil — mais difícil de manipular.
          </p>
        )}
      </div>

      {peg !== null && baseValue !== null && cagr !== null && (
        <div className="pe10-calc-details">
          <div className="pe10-calc-section">
            <div className="pe10-calc-section-title">Cálculo</div>
            <div className="pe10-calc-formula">
              <span>{baseLabel}</span>
              <span className="pe10-calc-formula-val">{br(baseValue, 2)}</span>
            </div>
            <div className="pe10-calc-formula">
              <span>CAGR {isEarnings ? "lucros reais" : "FCL real"}{method === "regression" ? " (regressão)" : ""}</span>
              <span className="pe10-calc-formula-val">{br(cagr, 2)}%</span>
            </div>
            <div className="pe10-calc-formula pe10-calc-result">
              <span>{br(baseValue, 2)} ÷ {br(cagr, 2)}</span>
              <span className="pe10-calc-formula-val">= {br(peg, 2)}</span>
            </div>
          </div>
          {method === "regression" && excludedYears.length > 0 && (
            <div className="pe10-calc-section">
              <div className="pe10-calc-section-title">Nota</div>
              <p className="modal-note">
                Anos com {isEarnings ? "lucro" : "FCL"} negativo/zero ({excludedYears.join(", ")}) foram
                excluídos. O CAGR foi estimado por regressão log-linear sobre os
                demais anos — método mais robusto que o cálculo ponto a ponto.
              </p>
            </div>
          )}
        </div>
      )}
    </>
  );
}

function CAGRInfo({ data, variant }: { data: QuoteData; variant: "earnings" | "fcf" }) {
  const isEarnings = variant === "earnings";
  const method = isEarnings ? data.earningsCAGRMethod : data.fcfCAGRMethod;
  const excludedYears = isEarnings ? data.earningsCAGRExcludedYears : data.fcfCAGRExcludedYears;
  const cagr = isEarnings ? data.earningsCAGR : data.fcfCAGR;

  return (
    <>
      <div className="modal-explainer">
        <p>
          <strong>CAGR</strong> (taxa de crescimento anual composta) mede o
          crescimento real {isEarnings ? "dos lucros líquidos" : "do fluxo de caixa livre"} ao
          longo do período disponível, ajustado pela inflação (IPCA).
        </p>
        {method === "endpoint" && (
          <p>
            O cálculo compara o {isEarnings ? "lucro" : "FCL"} ajustado do ano mais
            antigo com o mais recente: CAGR = (valor final / valor inicial)^(1/n) − 1.
            Valores negativos indicam que {isEarnings ? "os lucros" : "o FCL"} encolheram
            em termos reais.
          </p>
        )}
        {method === "regression" && (
          <p>
            Como houve anos com {isEarnings ? "lucro" : "FCL"} negativo ou zero
            ({excludedYears.join(", ")}), o CAGR foi estimado por <strong>regressão
            log-linear</strong> sobre os anos positivos — método mais robusto que usa
            todos os dados disponíveis em vez de depender apenas dos pontos extremos.
          </p>
        )}
        {method === null && (
          <p>
            O cálculo compara o {isEarnings ? "lucro" : "FCL"} ajustado do ano mais
            antigo com o mais recente: CAGR = (valor final / valor inicial)^(1/n) − 1.
          </p>
        )}
      </div>
      {cagr !== null && (
        <div className="pe10-calc-details">
          <div className="pe10-calc-section">
            <div className="pe10-calc-section-title">Resultado</div>
            <div className="pe10-calc-formula">
              <span>CAGR {isEarnings ? "lucros reais" : "FCL real"}{method === "regression" ? " (regressão)" : ""}</span>
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

const MODAL_TITLES: Record<string, (data: QuoteData) => string> = {
  debtToEquity: () => "Dív. Bruta / PL",
  debtExLease: () => "Dív - Arrend. / PL",
  liabToEquity: () => "Passivo / PL",
  debtToEarnings: () => "Dív. Bruta / Lucro Médio",
  debtToFCF: () => "Dív. Bruta / FCL Médio",
  pl10: (d) => ptLabel(d.pe10Label),
  peg: () => "PEG",
  cagrEarnings: () => "CAGR Lucros",
  pfcl10: (d) => ptLabel(d.pfcf10Label),
  pfclg: () => "PFCLG",
  cagrFCF: () => "CAGR FCL",
};

/* ── Main Card ── */

export function PE10Card({ data, years, maxYears, onYearsChange }: PE10CardProps) {
  const [activeModal, setActiveModal] = useState<ModalKey>(null);

  const pl10Label = ptLabel(data.pe10Label);
  const pfcl10Label = ptLabel(data.pfcf10Label);
  const open = (key: ModalKey) => setActiveModal(key);

  return (
    <article className="pe10-card" aria-label={`Indicadores de ${data.name} (${data.ticker})`}>
      <header className="pe10-card-header">
        {data.logo && (
          <img
            className="pe10-logo"
            src={data.logo}
            alt={`Logo ${data.name}`}
            onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
          />
        )}
        <h2 className="pe10-name">{data.name}</h2>
        <span className="pe10-ticker">{data.ticker}</span>
      </header>

      {/* ── Section: Dívida ── */}
      <div className="card-section">
        <div className="card-section-heading">Endividamento</div>

        {/* Leverage ratios */}
        <div className={`metrics-row leverage-row-top ${data.debtExLeaseToEquity !== null ? "leverage-row-3col" : ""}`}>
          <div className="metric-block">
            <div className="metric-value-container">
              <div className="pe10-label">Dív. Bruta / PL <InfoBtn onClick={() => open("debtToEquity")} /></div>
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
                <div className="pe10-label">Dív - Arrend. / PL <InfoBtn onClick={() => open("debtExLease")} /></div>
                <div className="pe10-value">{br(data.debtExLeaseToEquity, 2)}</div>
              </div>
            </div>
          )}
          <div className="metric-block">
            <div className="metric-value-container">
              <div className="pe10-label">Passivo / PL <InfoBtn onClick={() => open("liabToEquity")} /></div>
              {data.liabilitiesToEquity !== null ? (
                <div className="pe10-value">{br(data.liabilitiesToEquity, 2)}</div>
              ) : (
                <div className="pe10-error">{data.leverageError || "N/A"}</div>
              )}
            </div>
          </div>
        </div>

        {/* Debt coverage */}
        <div className="metrics-row leverage-row">
          <div className="metric-block">
            <div className="metric-value-container">
              <div className="pe10-label">Dív. Bruta / Lucro <span className="pe10-label-note">média {data.pe10YearsOfData}a</span> <InfoBtn onClick={() => open("debtToEarnings")} /></div>
              {data.debtToAvgEarnings !== null ? (
                <div className="pe10-value">{br(data.debtToAvgEarnings, 1)}</div>
              ) : (
                <div className="pe10-error">N/A</div>
              )}
            </div>
          </div>
          <div className="metric-block">
            <div className="metric-value-container">
              <div className="pe10-label">Dív. Bruta / FCL <span className="pe10-label-note">média {data.pfcf10YearsOfData}a</span> <InfoBtn onClick={() => open("debtToFCF")} /></div>
              {data.debtToAvgFCF !== null ? (
                <div className="pe10-value">{br(data.debtToAvgFCF, 1)}</div>
              ) : (
                <div className="pe10-error">N/A</div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* ── Section: Preço em relação a resultados ── */}
      <div className="card-section">
        <div className="card-section-heading">Preço em relação a {years} {years === 1 ? "ano" : "anos"} de resultados</div>

        {/* Earnings row: P/L10, PEG, CAGR Lucros */}
        <div className="metrics-row valuation-row">
          <div className="metric-block">
            <div className="metric-value-container">
              <div className="pe10-label">{pl10Label} <InfoBtn onClick={() => open("pl10")} /></div>
              {data.pe10 !== null ? (
                <div className="pe10-value">{br(data.pe10, 1)}</div>
              ) : (
                <div className="pe10-error">{data.pe10Error}</div>
              )}
            </div>
          </div>
          <div className="metric-block">
            <div className="metric-value-container">
              <div className="pe10-label">PEG <span className="pe10-label-note">Lynch</span> <InfoBtn onClick={() => open("peg")} /></div>
              {data.peg !== null ? (
                <div className="pe10-value">{br(data.peg, 2)}</div>
              ) : (
                <div className="pe10-error">{data.pegError || "N/A"}</div>
              )}
            </div>
          </div>
          <div className="metric-block">
            <div className="metric-value-container">
              <div className="pe10-label">CAGR Lucros <span className="pe10-label-note">real</span> <InfoBtn onClick={() => open("cagrEarnings")} /></div>
              {data.earningsCAGR !== null ? (
                <div className="pe10-value">{br(data.earningsCAGR, 1)}%</div>
              ) : (
                <div className="pe10-error">N/A</div>
              )}
            </div>
          </div>
        </div>

        {/* FCF row: P/FCL10, PFCLG, CAGR FCL */}
        <div className="metrics-row valuation-row">
          <div className="metric-block">
            <div className="metric-value-container">
              <div className="pe10-label">{pfcl10Label} <InfoBtn onClick={() => open("pfcl10")} /></div>
              {data.pfcf10 !== null ? (
                <div className="pe10-value">{br(data.pfcf10, 1)}</div>
              ) : (
                <div className="pe10-error">{data.pfcf10Error}</div>
              )}
            </div>
          </div>
          <div className="metric-block">
            <div className="metric-value-container">
              <div className="pe10-label">PFCLG <span className="pe10-label-note">Lynch</span> <InfoBtn onClick={() => open("pfclg")} /></div>
              {data.pfcfPeg !== null ? (
                <div className="pe10-value">{br(data.pfcfPeg, 2)}</div>
              ) : (
                <div className="pe10-error">{data.pfcfPegError || "N/A"}</div>
              )}
            </div>
          </div>
          <div className="metric-block">
            <div className="metric-value-container">
              <div className="pe10-label">CAGR FCL <span className="pe10-label-note">real</span> <InfoBtn onClick={() => open("cagrFCF")} /></div>
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
              Analisando os últimos <strong>{years} {years === 1 ? "ano" : "anos"}</strong> de resultados.
              Arraste para alterar o horizonte e ver como os indicadores de
              valuation mudam conforme o período considerado.
            </p>
          </div>
        )}
      </div>

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
            R$ {br(data.currentPrice, 2)}
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

      {activeModal && (
        <Modal
          title={`${MODAL_TITLES[activeModal]?.(data) ?? ""} — ${data.name}`}
          onClose={() => setActiveModal(null)}
        >
          <ModalContent modalKey={activeModal} data={data} />
        </Modal>
      )}
    </article>
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
