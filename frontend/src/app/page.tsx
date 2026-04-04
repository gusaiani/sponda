"use client";

import Link from "next/link";
import { HomepageGrid } from "../components/HomepageGrid";
import { PopularCompanies } from "../components/PopularCompanies";
import { ShareButtons } from "../components/ShareButtons";
import { useTranslation } from "../i18n";

export default function HomePage() {
  const { locale } = useTranslation();

  return (
    <div>
      <HomepageGrid />

      <PopularCompanies />

      {/* Hidden SEO article — provides crawlable text for search engines */}
      {locale === "pt" ? (
        <article className="homepage-explainer" style={{ position: "absolute", width: 1, height: 1, overflow: "hidden", clip: "rect(0,0,0,0)", whiteSpace: "nowrap" }}>
          <h2 className="homepage-explainer-title">Análise fundamentalista de ações brasileiras ajustada pela inflação</h2>
          <p>
            O Sponda é uma plataforma de análise fundamentalista para investidores em valor.
            Calcula indicadores de valuation, rentabilidade, crescimento e alavancagem para
            todas as ações da B3, ajustados pela inflação (IPCA).
          </p>
          <h3>Indicadores de valuation</h3>
          <p>
            O <strong>PE10</strong> (Shiller PE / CAPE) utiliza a média dos lucros dos últimos
            10 anos corrigidos pela inflação, reduzindo o efeito de ciclos econômicos.
            O <strong>PFCF10</strong> aplica a mesma lógica ao fluxo de caixa livre.
            O <strong>PEG</strong> divide o PE10 pelo CAGR dos lucros, e o <strong>PFCLG</strong> faz
            o mesmo com o fluxo de caixa. O <strong>P/VPA</strong> compara o preço ao valor
            patrimonial por ação. Todos os períodos são ajustáveis de 1 a 10 anos.
          </p>
          <h3>Crescimento e rentabilidade</h3>
          <p>
            O <strong>CAGR</strong> do lucro e do fluxo de caixa livre mede o crescimento
            composto ao longo do período selecionado. O <strong>ROE</strong> (retorno sobre o
            patrimônio líquido) avalia a rentabilidade da empresa.
          </p>
          <h3>Alavancagem e solvência</h3>
          <p>
            Indicadores de endividamento incluem <strong>Dívida/PL</strong>,{" "}
            <strong>Dívida-Arrend/PL</strong> (excluindo arrendamentos),{" "}
            <strong>Passivo/PL</strong>, <strong>Liquidez Corrente</strong>,{" "}
            <strong>Dívida/Lucro</strong> e <strong>Dívida/FCL</strong> (tempo de
            pagamento da dívida em anos).
          </p>
          <h3>Fundamentos históricos</h3>
          <p>
            A aba de fundamentos exibe dados anuais do balanço patrimonial, demonstração de
            resultados e fluxo de caixa, com opção de visualizar valores nominais ou
            corrigidos pela inflação.
          </p>
          <h3>Gráficos</h3>
          <p>
            Gráficos interativos mostram o histórico de preço junto com a evolução do PE10
            ou PFCF10, permitindo identificar momentos de sobre ou subvalorização.
          </p>
          <h3>Comparação de empresas</h3>
          <p>
            Compare múltiplas empresas lado a lado em todos os indicadores. Salve listas de
            comparação, reordene, compartilhe via link e acesse empresas do mesmo setor
            automaticamente.
          </p>
          <h3>Favoritos e listas</h3>
          <p>
            Adicione empresas aos favoritos para acesso rápido. Crie e salve listas de
            comparação personalizadas, reordene a exibição e compartilhe com outros investidores.
          </p>
          <p>
            Explore os indicadores de empresas como{" "}
            <Link href="/PETR4">PETR4</Link>,{" "}
            <Link href="/VALE3">VALE3</Link>,{" "}
            <Link href="/ITUB4">ITUB4</Link>,{" "}
            <Link href="/WEGE3">WEGE3</Link> e{" "}
            <Link href="/ABEV3">ABEV3</Link>, ou
            busque qualquer ação da B3 na barra de pesquisa.
          </p>
        </article>
      ) : (
        <article className="homepage-explainer" style={{ position: "absolute", width: 1, height: 1, overflow: "hidden", clip: "rect(0,0,0,0)", whiteSpace: "nowrap" }}>
          <h2 className="homepage-explainer-title">Inflation-adjusted fundamental analysis of Brazilian stocks</h2>
          <p>
            Sponda is a fundamental analysis platform for value investors.
            It calculates valuation, profitability, growth and leverage indicators for
            all B3 stocks, adjusted for inflation (IPCA).
          </p>
          <h3>Valuation indicators</h3>
          <p>
            <strong>PE10</strong> (Shiller PE / CAPE) uses the average of the last 10 years
            of inflation-adjusted earnings, reducing the effect of economic cycles.
            <strong>PFCF10</strong> applies the same logic to free cash flow.
            <strong>PEG</strong> divides PE10 by earnings CAGR, and <strong>PFCLG</strong> does
            the same with cash flow. <strong>P/BV</strong> compares price to book value
            per share. All periods are adjustable from 1 to 10 years.
          </p>
          <h3>Growth and profitability</h3>
          <p>
            <strong>CAGR</strong> of earnings and free cash flow measures compound growth
            over the selected period. <strong>ROE</strong> (return on equity) evaluates
            the company&apos;s profitability.
          </p>
          <h3>Leverage and solvency</h3>
          <p>
            Leverage indicators include <strong>Debt/Equity</strong>,{" "}
            <strong>Debt ex Lease/Equity</strong> (excluding leases),{" "}
            <strong>Liabilities/Equity</strong>, <strong>Current Ratio</strong>,{" "}
            <strong>Debt/Earnings</strong> and <strong>Debt/FCF</strong> (years to
            pay off debt).
          </p>
          <h3>Historical fundamentals</h3>
          <p>
            The fundamentals tab shows annual balance sheet, income statement and
            cash flow data, with the option to view nominal or inflation-adjusted values.
          </p>
          <h3>Charts</h3>
          <p>
            Interactive charts show price history alongside PE10 or PFCF10 evolution,
            helping identify moments of over or undervaluation.
          </p>
          <h3>Company comparison</h3>
          <p>
            Compare multiple companies side by side across all indicators. Save comparison
            lists, reorder, share via link and access same-sector companies automatically.
          </p>
          <h3>Favorites and lists</h3>
          <p>
            Add companies to favorites for quick access. Create and save custom comparison
            lists, reorder the display and share with other investors.
          </p>
          <p>
            Explore indicators for companies like{" "}
            <Link href="/PETR4">PETR4</Link>,{" "}
            <Link href="/VALE3">VALE3</Link>,{" "}
            <Link href="/ITUB4">ITUB4</Link>,{" "}
            <Link href="/WEGE3">WEGE3</Link> and{" "}
            <Link href="/ABEV3">ABEV3</Link>, or
            search for any B3 stock in the search bar.
          </p>
        </article>
      )}

      <ShareButtons />
    </div>
  );
}
