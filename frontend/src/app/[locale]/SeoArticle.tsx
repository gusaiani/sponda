import Link from "next/link";
import { ARTICLES } from "../../lib/site-copy";

const SEO_STYLE = {
  position: "absolute" as const,
  width: 1,
  height: 1,
  overflow: "hidden" as const,
  clip: "rect(0,0,0,0)",
  whiteSpace: "nowrap" as const,
};

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


const INTRO: Record<string, string> = {
  pt: "é uma plataforma de análise fundamentalista para investidores em valor.",
  en: "is a fundamental analysis platform for value investors.",
  es: "es una plataforma de análisis fundamental para inversores en valor.",
  zh: "是一个面向价值投资者的基本面分析平台。",
  fr: "est une plateforme d'analyse fondamentale pour investisseurs value.",
  de: "ist eine Fundamentalanalyse-Plattform für Value-Investoren.",
  it: "è una piattaforma di analisi fondamentale per investitori di valore.",
};

export function SeoArticle({ locale }: { locale: string }) {
  const article = ARTICLES[locale] || ARTICLES.en;
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
