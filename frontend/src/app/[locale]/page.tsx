"use client";

import Link from "next/link";
import { HomepageGrid } from "../../components/HomepageGrid";
import { PopularCompanies } from "../../components/PopularCompanies";
import { ShareButtons } from "../../components/ShareButtons";
import { useTranslation } from "../../i18n";

const SEO_STYLE = { position: "absolute" as const, width: 1, height: 1, overflow: "hidden" as const, clip: "rect(0,0,0,0)", whiteSpace: "nowrap" as const };

const TICKERS = ["PETR4", "VALE3", "ITUB4", "WEGE3", "ABEV3"];

function TickerLinks({ locale }: { locale: string }) {
  return (
    <>
      {TICKERS.map((ticker, index) => (
        <span key={ticker}>
          {index > 0 && ", "}
          <Link href={`/${locale}/${ticker}`}>{ticker}</Link>
        </span>
      ))}
    </>
  );
}

function SeoArticle({ locale }: { locale: string }) {
  const ARTICLES: Record<string, { title: string; sections: { heading: string; text: string }[] }> = {
    pt: {
      title: "Análise fundamentalista ajustada pela inflação para investidores em valor",
      sections: [
        { heading: "Indicadores de valuation", text: "O PE10 (Shiller PE / CAPE) utiliza a média dos lucros dos últimos 10 anos corrigidos pela inflação, reduzindo o efeito de ciclos econômicos. O PFCF10 aplica a mesma lógica ao fluxo de caixa livre. O PEG divide o PE10 pelo CAGR dos lucros, e o PFCLG faz o mesmo com o fluxo de caixa. O P/VPA compara o preço ao valor patrimonial por ação. Todos os períodos são ajustáveis de 1 a 10 anos." },
        { heading: "Crescimento e rentabilidade", text: "O CAGR do lucro e do fluxo de caixa livre mede o crescimento composto ao longo do período selecionado. O ROE (retorno sobre o patrimônio líquido) avalia a rentabilidade da empresa." },
        { heading: "Alavancagem e solvência", text: "Indicadores de endividamento incluem Dívida/PL, Dívida-Arrend/PL (excluindo arrendamentos), Passivo/PL, Liquidez Corrente, Dívida/Lucro e Dívida/FCL (tempo de pagamento da dívida em anos)." },
        { heading: "Fundamentos históricos", text: "A aba de fundamentos exibe dados anuais do balanço patrimonial, demonstração de resultados e fluxo de caixa, com opção de visualizar valores nominais ou corrigidos pela inflação." },
        { heading: "Gráficos", text: "Gráficos interativos mostram o histórico de preço junto com a evolução do PE10 ou PFCF10, permitindo identificar momentos de sobre ou subvalorização." },
        { heading: "Comparação de empresas", text: "Compare múltiplas empresas lado a lado em todos os indicadores. Salve listas de comparação, reordene, compartilhe via link e acesse empresas do mesmo setor automaticamente." },
      ],
    },
    en: {
      title: "Inflation-adjusted fundamental analysis for value investors",
      sections: [
        { heading: "Valuation indicators", text: "PE10 (Shiller PE / CAPE) uses the average of the last 10 years of inflation-adjusted earnings, reducing the effect of economic cycles. PFCF10 applies the same logic to free cash flow. PEG divides PE10 by earnings CAGR, and PFCLG does the same with cash flow. P/BV compares price to book value per share. All periods are adjustable from 1 to 10 years." },
        { heading: "Growth and profitability", text: "CAGR of earnings and free cash flow measures compound growth over the selected period. ROE (return on equity) evaluates the company's profitability." },
        { heading: "Leverage and solvency", text: "Leverage indicators include Debt/Equity, Debt ex Lease/Equity (excluding leases), Liabilities/Equity, Current Ratio, Debt/Earnings and Debt/FCF (years to pay off debt)." },
        { heading: "Historical fundamentals", text: "The fundamentals tab shows annual balance sheet, income statement and cash flow data, with the option to view nominal or inflation-adjusted values." },
        { heading: "Charts", text: "Interactive charts show price history alongside PE10 or PFCF10 evolution, helping identify moments of over or undervaluation." },
        { heading: "Company comparison", text: "Compare multiple companies side by side across all indicators. Save comparison lists, reorder, share via link and access same-sector companies automatically." },
      ],
    },
    es: {
      title: "Análisis fundamental ajustado por inflación para inversores en valor",
      sections: [
        { heading: "Indicadores de valoración", text: "El PE10 (Shiller PE / CAPE) utiliza el promedio de los beneficios de los últimos 10 años ajustados por inflación, reduciendo el efecto de los ciclos económicos. El PFCF10 aplica la misma lógica al flujo de caja libre. El PEG divide el PE10 por el CAGR de beneficios, y el PFCLG hace lo mismo con el flujo de caja. El P/VC compara el precio con el valor contable por acción. Todos los períodos son ajustables de 1 a 10 años." },
        { heading: "Crecimiento y rentabilidad", text: "El CAGR de beneficios y flujo de caja libre mide el crecimiento compuesto a lo largo del período seleccionado. El ROE (rentabilidad sobre el patrimonio) evalúa la rentabilidad de la empresa." },
        { heading: "Apalancamiento y solvencia", text: "Los indicadores de endeudamiento incluyen Deuda/Patrimonio, Deuda sin Arrendamiento/Patrimonio, Pasivo/Patrimonio, Razón Corriente, Deuda/Beneficios y Deuda/FCF (años para pagar la deuda)." },
        { heading: "Fundamentos históricos", text: "La pestaña de fundamentos muestra datos anuales de balance, estado de resultados y flujo de caja, con la opción de ver valores nominales o ajustados por inflación." },
        { heading: "Gráficos", text: "Gráficos interactivos muestran el historial de precios junto con la evolución del PE10 o PFCF10, ayudando a identificar momentos de sobre o subvaloración." },
        { heading: "Comparación de empresas", text: "Compare múltiples empresas lado a lado en todos los indicadores. Guarde listas de comparación, reordene, comparta por enlace y acceda a empresas del mismo sector automáticamente." },
      ],
    },
    zh: {
      title: "通胀调整基本面分析 · 价值投资者工具",
      sections: [
        { heading: "估值指标", text: "PE10（席勒市盈率 / CAPE）使用过去10年经通胀调整的平均盈利，减少经济周期的影响。PFCF10 将同样的逻辑应用于自由现金流。PEG 将 PE10 除以盈利 CAGR，PFCLG 对现金流做同样的计算。P/BV 将价格与每股账面价值进行比较。所有周期可在1至10年间调整。" },
        { heading: "增长和盈利能力", text: "盈利和自由现金流的 CAGR 衡量选定期间的复合增长。ROE（股本回报率）评估公司的盈利能力。" },
        { heading: "杠杆和偿债能力", text: "杠杆指标包括债务/股东权益、债务（不含租赁）/股东权益、总负债/股东权益、流动比率、债务/盈利和债务/FCF（偿还债务所需年数）。" },
        { heading: "历史基本面", text: "基本面选项卡显示年度资产负债表、利润表和现金流量表数据，可选择查看名义值或通胀调整值。" },
        { heading: "图表", text: "交互式图表显示价格历史以及 PE10 或 PFCF10 的演变，帮助识别高估或低估的时刻。" },
        { heading: "公司对比", text: "在所有指标上并排比较多家公司。保存对比列表、重新排序、通过链接分享，并自动访问同行业公司。" },
      ],
    },
    fr: {
      title: "Analyse fondamentale ajustée de l'inflation pour investisseurs value",
      sections: [
        { heading: "Indicateurs de valorisation", text: "Le PE10 (Shiller PE / CAPE) utilise la moyenne des bénéfices des 10 dernières années ajustés de l'inflation, réduisant l'effet des cycles économiques. Le PFCF10 applique la même logique au flux de trésorerie libre. Le PEG divise le PE10 par le CAGR des bénéfices, et le PFCLG fait de même avec les flux de trésorerie. Le P/VC compare le prix à la valeur comptable par action. Toutes les périodes sont ajustables de 1 à 10 ans." },
        { heading: "Croissance et rentabilité", text: "Le CAGR des bénéfices et du flux de trésorerie libre mesure la croissance composée sur la période sélectionnée. Le ROE (rentabilité des capitaux propres) évalue la rentabilité de l'entreprise." },
        { heading: "Endettement et solvabilité", text: "Les indicateurs d'endettement comprennent Dette/Capitaux Propres, Dette hors Location/Capitaux Propres, Passif/Capitaux Propres, Ratio de Liquidité, Dette/Bénéfices et Dette/FCF (années pour rembourser la dette)." },
        { heading: "Fondamentaux historiques", text: "L'onglet fondamentaux affiche les données annuelles du bilan, du compte de résultat et des flux de trésorerie, avec la possibilité de consulter les valeurs nominales ou ajustées de l'inflation." },
        { heading: "Graphiques", text: "Des graphiques interactifs montrent l'historique des prix aux côtés de l'évolution du PE10 ou PFCF10, aidant à identifier les moments de sur ou sous-évaluation." },
        { heading: "Comparaison d'entreprises", text: "Comparez plusieurs entreprises côte à côte sur tous les indicateurs. Sauvegardez des listes de comparaison, réordonnez, partagez par lien et accédez automatiquement aux entreprises du même secteur." },
      ],
    },
    de: {
      title: "Inflationsbereinigte Fundamentalanalyse für Value-Investoren",
      sections: [
        { heading: "Bewertungskennzahlen", text: "Das PE10 (Shiller KGV / CAPE) verwendet den Durchschnitt der inflationsbereinigten Gewinne der letzten 10 Jahre und reduziert so den Effekt von Konjunkturzyklen. PFCF10 wendet die gleiche Logik auf den freien Cashflow an. PEG teilt PE10 durch die Gewinn-CAGR, und PFCLG macht dasselbe mit dem Cashflow. KBV vergleicht den Kurs mit dem Buchwert je Aktie. Alle Zeiträume sind von 1 bis 10 Jahren einstellbar." },
        { heading: "Wachstum und Rentabilität", text: "Die CAGR von Gewinn und freiem Cashflow misst das zusammengesetzte Wachstum über den gewählten Zeitraum. Die ROE (Eigenkapitalrendite) bewertet die Rentabilität des Unternehmens." },
        { heading: "Verschuldung und Solvenz", text: "Verschuldungskennzahlen umfassen Schulden/Eigenkapital, Schulden ohne Leasing/Eigenkapital, Verbindlichkeiten/Eigenkapital, Liquiditätsquote, Schulden/Gewinn und Schulden/FCF (Jahre zur Schuldentilgung)." },
        { heading: "Historische Fundamentaldaten", text: "Der Fundamentaldaten-Tab zeigt jährliche Bilanz-, Gewinn- und Verlustrechnung sowie Cashflow-Daten, mit der Option nominale oder inflationsbereinigte Werte anzuzeigen." },
        { heading: "Diagramme", text: "Interaktive Diagramme zeigen die Kurshistorie neben der Entwicklung von PE10 oder PFCF10 und helfen, Momente der Über- oder Unterbewertung zu erkennen." },
        { heading: "Unternehmensvergleich", text: "Vergleichen Sie mehrere Unternehmen nebeneinander über alle Kennzahlen. Speichern Sie Vergleichslisten, ordnen Sie neu, teilen Sie per Link und greifen Sie automatisch auf Unternehmen der gleichen Branche zu." },
      ],
    },
    it: {
      title: "Analisi fondamentale corretta per l'inflazione per investitori di valore",
      sections: [
        { heading: "Indicatori di valutazione", text: "Il PE10 (Shiller PE / CAPE) utilizza la media degli utili degli ultimi 10 anni corretti per l'inflazione, riducendo l'effetto dei cicli economici. Il PFCF10 applica la stessa logica al flusso di cassa libero. Il PEG divide il PE10 per il CAGR degli utili, e il PFCLG fa lo stesso con il flusso di cassa. Il P/PN confronta il prezzo con il patrimonio netto per azione. Tutti i periodi sono regolabili da 1 a 10 anni." },
        { heading: "Crescita e redditività", text: "Il CAGR degli utili e del flusso di cassa libero misura la crescita composta nel periodo selezionato. Il ROE (rendimento del capitale proprio) valuta la redditività dell'azienda." },
        { heading: "Leva finanziaria e solvibilità", text: "Gli indicatori di indebitamento includono Debito/Patrimonio Netto, Debito senza Leasing/Patrimonio Netto, Passività/Patrimonio Netto, Rapporto di Liquidità, Debito/Utili e Debito/FCF (anni per estinguere il debito)." },
        { heading: "Fondamentali storici", text: "La scheda fondamentali mostra i dati annuali di bilancio, conto economico e flusso di cassa, con l'opzione di visualizzare valori nominali o corretti per l'inflazione." },
        { heading: "Grafici", text: "Grafici interattivi mostrano lo storico dei prezzi insieme all'evoluzione del PE10 o PFCF10, aiutando a identificare momenti di sopra o sottovalutazione." },
        { heading: "Confronto aziende", text: "Confronta più aziende fianco a fianco su tutti gli indicatori. Salva liste di confronto, riordina, condividi tramite link e accedi automaticamente alle aziende dello stesso settore." },
      ],
    },
  };

  const article = ARTICLES[locale] || ARTICLES.en;

  const INTRO: Record<string, string> = {
    pt: "é uma plataforma de análise fundamentalista para investidores em valor.",
    en: "is a fundamental analysis platform for value investors.",
    es: "es una plataforma de análisis fundamental para inversores en valor.",
    zh: "是一个面向价值投资者的基本面分析平台。",
    fr: "est une plateforme d'analyse fondamentale pour investisseurs value.",
    de: "ist eine Fundamentalanalyse-Plattform für Value-Investoren.",
    it: "è una piattaforma di analisi fondamentale per investitori di valore.",
  };

  return (
    <article className="homepage-explainer" style={SEO_STYLE}>
      <h2 className="homepage-explainer-title">{article.title}</h2>
      <p>Sponda {INTRO[locale] || INTRO.en}</p>
      {article.sections.map((section) => (
        <div key={section.heading}>
          <h3>{section.heading}</h3>
          <p>{section.text}</p>
        </div>
      ))}
      <p><TickerLinks locale={locale} /></p>
    </article>
  );
}

export default function HomePage() {
  const { locale } = useTranslation();

  return (
    <div>
      <HomepageGrid />

      <PopularCompanies />

      {/* Hidden SEO article — provides crawlable text for search engines */}
      <SeoArticle locale={locale} />

      <ShareButtons />
    </div>
  );
}
