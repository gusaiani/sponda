"use client";

import Link from "next/link";
import { HomepageGrid } from "../components/HomepageGrid";
import { PopularCompanies } from "../components/PopularCompanies";
import { ShareButtons } from "../components/ShareButtons";

export default function HomePage() {
  return (
    <div>
      <HomepageGrid />

      <PopularCompanies />

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

      <ShareButtons />
    </div>
  );
}
