import { LOCALE_TO_HTML_LANG, type SupportedLocale } from "./i18n-config";

const BASE_URL = "https://sponda.capital";
const SITE_NAME = "Sponda";
const ORGANIZATION_LOGO_URL = `${BASE_URL}/sponda-logo-2026-03-20.png`;

const SITE_DESCRIPTION: Record<SupportedLocale, string> = {
  pt: "Indicadores fundamentalistas para investidores em valor. P/L ajustado pela inflação (Shiller PE), P/FCL, PEG, CAGR, alavancagem e mais.",
  en: "Fundamental indicators for value investors. Inflation-adjusted P/E (Shiller PE), P/FCF, PEG, CAGR, leverage ratios and more.",
  es: "Indicadores fundamentales para inversores en valor. P/E ajustado por inflación (Shiller PE), P/FCF, PEG, CAGR, apalancamiento y más.",
  zh: "价值投资者基本面指标。通胀调整市盈率 (Shiller PE)、P/FCF、PEG、CAGR、杠杆率等。",
  fr: "Indicateurs fondamentaux pour investisseurs value. P/E ajusté de l'inflation (Shiller PE), P/FCF, PEG, CAGR, endettement et plus.",
  de: "Fundamentalkennzahlen für Value-Investoren. Inflationsbereinigtes KGV (Shiller PE), P/FCF, PEG, CAGR, Verschuldung und mehr.",
  it: "Indicatori fondamentali per investitori di valore. P/E corretto per l'inflazione (Shiller PE), P/FCF, PEG, CAGR, leva finanziaria e altro.",
};

export type StructuredDataSchema = Record<string, unknown> & { "@type": string };

/**
 * The site-level JSON-LD every page carries: what the site is and who
 * publishes it.
 *
 * This used to be a single `WebApplication`. Google's rich-result rules for
 * SoftwareApplication (which WebApplication inherits) require an
 * `aggregateRating` or a `review`, neither of which exists, so every page on
 * the domain failed structured-data validation. `WebSite` and `Organization`
 * have no such requirement and say the same thing.
 */
export function buildSiteStructuredData(locale: SupportedLocale): StructuredDataSchema[] {
  const description = SITE_DESCRIPTION[locale];
  const organization: StructuredDataSchema = {
    "@context": "https://schema.org",
    "@type": "Organization",
    name: SITE_NAME,
    url: BASE_URL,
    logo: ORGANIZATION_LOGO_URL,
    parentOrganization: {
      "@type": "Organization",
      name: "Poema Parceria de Investimentos",
      url: "https://poe.ma",
    },
  };
  const website: StructuredDataSchema = {
    "@context": "https://schema.org",
    "@type": "WebSite",
    name: SITE_NAME,
    url: BASE_URL,
    description,
    inLanguage: LOCALE_TO_HTML_LANG[locale],
    publisher: { "@type": "Organization", name: SITE_NAME, url: BASE_URL },
  };
  return [website, organization];
}
