import type { Metadata } from "next";
import { SUPPORTED_LOCALES, LOCALE_TO_OG_LOCALE, LOCALE_TO_HTML_LANG, type SupportedLocale } from "./i18n-config";
import { tabSlugForLocale, type TabKey } from "../utils/tabs";
import { djangoApiBaseUrl } from "./django-api";
import { markdownUrlFor } from "./markdown-routes";
import { ogImageUrlForTicker, siteOgImageUrlForLocale } from "./og-card";

const BASE_URL = "https://sponda.capital";

const OG_IMAGE_WIDTH = 1200;
const OG_IMAGE_HEIGHT = 630;
const OG_IMAGE_MIME_TYPE = "image/jpeg";
const TICKER_OG_IMAGE_MIME_TYPE = "image/png";
const OG_IMAGE_ALT_TEXT = "Sponda · fundamental indicators for value investors";

/**
 * Path to the OG image for pages with no single company to render.
 *
 * The Portuguese card carries the Portuguese tagline; every other locale
 * falls back to the English card. Both are served by
 * `src/app/og/site/[card]/route.ts` rather than straight out of
 * `public/images/`, at a URL no social network had seen before, with a
 * `Content-Length` and no validators. See `src/lib/og-response.ts`, and
 * the OG images section of the README for the months-long X saga behind
 * this (a robots.txt wildcard and an RSC `Vary` header, in the end).
 */
export function getOgImageUrl(locale: string): string {
  return siteOgImageUrlForLocale(locale);
}

/** The `openGraph.images` entry for pages with no single company to render. */
export function buildOgImageDescriptor(locale: string) {
  return {
    url: `${BASE_URL}${getOgImageUrl(locale)}`,
    width: OG_IMAGE_WIDTH,
    height: OG_IMAGE_HEIGHT,
    type: OG_IMAGE_MIME_TYPE,
    alt: OG_IMAGE_ALT_TEXT,
  };
}

/**
 * The `openGraph.images` entry for one company, pointing at the card that
 * `src/app/og/[locale]/[ticker]/route.tsx` renders on demand.
 *
 * A distinct URL per company per locale is the point: social networks key
 * their image caches by URL, so no single entry can take every preview on
 * the domain down with it.
 */
export function buildTickerOgImageDescriptor(
  locale: string,
  ticker: string,
  companyName: string,
) {
  return {
    url: `${BASE_URL}${ogImageUrlForTicker(locale, ticker)}`,
    width: OG_IMAGE_WIDTH,
    height: OG_IMAGE_HEIGHT,
    type: TICKER_OG_IMAGE_MIME_TYPE,
    alt: companyName
      ? `${companyName} (${ticker}) · Sponda`
      : `${ticker} · Sponda`,
  };
}

interface TickerInfo {
  name: string;
  sector: string;
}

async function fetchTickerInfo(ticker: string): Promise<TickerInfo | null> {
  const djangoUrl = djangoApiBaseUrl();
  try {
    const response = await fetch(`${djangoUrl}/api/tickers/${ticker}/`, { next: { revalidate: 3600 } });
    if (!response.ok) return null;
    const found = await response.json();
    return { name: found.name, sector: found.sector };
  } catch {
    return null;
  }
}

/** Map a tab slug to its TabKey. */
const SLUG_TO_TAB: Record<string, TabKey> = {
  graficos: "charts", charts: "charts", graphiques: "charts", diagramme: "charts",
  fundamentos: "fundamentals", fundamentals: "fundamentals", fondamentaux: "fundamentals", fundamentaldaten: "fundamentals",
  comparar: "compare", compare: "compare", comparer: "compare", vergleich: "compare", confronta: "compare",
  grafici: "charts", fondamentali: "fundamentals",
};

/** Localized tab display names for breadcrumbs. */
const TAB_DISPLAY: Record<string, Record<string, string>> = {
  pt: { graficos: "Gráficos", fundamentos: "Fundamentos", comparar: "Comparar" },
  en: { charts: "Charts", fundamentals: "Fundamentals", compare: "Compare" },
  es: { graficos: "Gráficos", fundamentos: "Fundamentos", comparar: "Comparar" },
  zh: { charts: "图表", fundamentals: "基本面", compare: "对比" },
  fr: { graphiques: "Graphiques", fondamentaux: "Fondamentaux", comparer: "Comparer" },
  de: { diagramme: "Diagramme", fundamentaldaten: "Fundamentaldaten", vergleich: "Vergleich" },
  it: { grafici: "Grafici", fondamentali: "Fondamentali", confronta: "Confronta" },
};

/** Locale-specific title suffix. */
const TITLE_SUFFIX: Record<string, string> = {
  pt: "Indicadores Fundamentalistas",
  en: "Fundamental Indicators",
  es: "Indicadores Fundamentales",
  zh: "基本面指标",
  fr: "Indicateurs Fondamentaux",
  de: "Fundamentalkennzahlen",
  it: "Indicatori Fondamentali",
};

/** Locale-specific description templates. */
function buildDescription(locale: SupportedLocale, ticker: string, companyName: string): string {
  const name = companyName || ticker;
  switch (locale) {
    case "pt":
      return `Indicadores fundamentalistas de ${name} (${ticker}): P/L ajustado pela inflação (PE10), P/FCL10, PEG, CAGR e alavancagem. Dados atualizados.`;
    case "en":
      return `Fundamental indicators for ${name} (${ticker}): inflation-adjusted P/E (PE10), P/FCF10, PEG, CAGR and leverage. Updated data.`;
    case "es":
      return `Indicadores fundamentales de ${name} (${ticker}): P/E ajustado por inflación (PE10), P/FCF10, PEG, CAGR y apalancamiento. Datos actualizados.`;
    case "zh":
      return `${name} (${ticker}) 基本面指标：通胀调整市盈率 (PE10)、P/FCF10、PEG、CAGR 及杠杆率。数据持续更新。`;
    case "fr":
      return `Indicateurs fondamentaux de ${name} (${ticker}) : P/E ajusté de l'inflation (PE10), P/FCF10, PEG, CAGR et endettement. Données actualisées.`;
    case "de":
      return `Fundamentalkennzahlen für ${name} (${ticker}): inflationsbereinigtes KGV (PE10), P/FCF10, PEG, CAGR und Verschuldung. Aktuelle Daten.`;
    case "it":
      return `Indicatori fondamentali di ${name} (${ticker}): P/E corretto per l'inflazione (PE10), P/FCF10, PEG, CAGR e leva finanziaria. Dati aggiornati.`;
  }
}

/** Locale-specific keywords. */
const KEYWORDS: Record<string, string[]> = {
  pt: ["PE10", "PFCF10", "PEG", "CAGR", "análise fundamentalista", "investimento em valor", "mercado de ações"],
  en: ["PE10", "PFCF10", "PEG", "CAGR", "fundamental analysis", "stock market", "value investing"],
  es: ["PE10", "PFCF10", "PEG", "CAGR", "análisis fundamental", "inversión en valor", "mercado de valores"],
  zh: ["PE10", "PFCF10", "PEG", "CAGR", "基本面分析", "价值投资", "股票市场"],
  fr: ["PE10", "PFCF10", "PEG", "CAGR", "analyse fondamentale", "investissement valeur", "marché boursier"],
  de: ["PE10", "PFCF10", "PEG", "CAGR", "Fundamentalanalyse", "Value-Investing", "Aktienmarkt"],
  it: ["PE10", "PFCF10", "PEG", "CAGR", "analisi fondamentale", "investimento di valore", "mercato azionario"],
};

export async function generateTickerMetadata(
  ticker: string,
  locale: SupportedLocale,
  tabSlug?: string,
): Promise<Metadata> {
  const info = await fetchTickerInfo(ticker);
  const companyName = info?.name || "";
  const sector = info?.sector || "";

  // Build locale-specific path
  const localePath = tabSlug ? `${locale}/${ticker}/${tabSlug}` : `${locale}/${ticker}`;
  const markdownTab = tabSlug ? (SLUG_TO_TAB[tabSlug] ?? "metrics") : "metrics";
  const url = `${BASE_URL}/${localePath}`;

  // Build alternates for all supported locales
  const alternateLanguages: Record<string, string> = {};
  for (const altLocale of SUPPORTED_LOCALES) {
    let altTabSlug: string | undefined;
    if (tabSlug) {
      const tabKey = SLUG_TO_TAB[tabSlug];
      altTabSlug = tabKey ? tabSlugForLocale(altLocale, tabKey) : tabSlug;
    }
    const altPath = altTabSlug
      ? `${BASE_URL}/${altLocale}/${ticker}/${altTabSlug}`
      : `${BASE_URL}/${altLocale}/${ticker}`;
    const langKey = LOCALE_TO_HTML_LANG[altLocale].replace("-", "_") === "pt_BR" ? "pt-BR" : altLocale;
    alternateLanguages[langKey] = altPath;
  }
  alternateLanguages["x-default"] = alternateLanguages["en"];

  // Locale-specific title and description
  const suffix = TITLE_SUFFIX[locale];
  const title = companyName
    ? `${companyName} (${ticker}) · ${suffix} · Sponda`
    : `${ticker} · ${suffix} · Sponda`;
  const description = buildDescription(locale, ticker, companyName);

  const ogLocale = LOCALE_TO_OG_LOCALE[locale];
  const htmlLang = LOCALE_TO_HTML_LANG[locale];
  const tickerOgImage = buildTickerOgImageDescriptor(locale, ticker, companyName);

  // Breadcrumb tab name
  const tabDisplayName = tabSlug
    ? (TAB_DISPLAY[locale]?.[tabSlug] || tabSlug)
    : undefined;

  const metadata: Metadata = {
    title,
    description,
    alternates: {
      canonical: url,
      languages: alternateLanguages,
      // The plain-markdown twin of this page. A crawler that parses link
      // alternates finds it here; one that does not can still guess it,
      // which is the whole point of the .md suffix convention.
      types: {
        "text/markdown": `${BASE_URL}${markdownUrlFor(locale, ticker, markdownTab)}`,
      },
    },
    openGraph: {
      type: "website",
      title,
      description,
      url,
      images: [tickerOgImage],
      locale: ogLocale,
      siteName: "Sponda",
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: [tickerOgImage.url],
    },
    other: {
      "structured-data": JSON.stringify([
        {
          "@context": "https://schema.org",
          "@type": "Dataset",
          name: `${suffix} ${locale === "zh" ? "：" : locale === "de" ? " für " : locale === "fr" ? " de " : " · "}${companyName || ticker} (${ticker})`,
          description,
          url,
          keywords: [ticker, companyName || ticker, ...(KEYWORDS[locale] || KEYWORDS.en)],
          creator: { "@type": "Organization", name: "Sponda", url: BASE_URL },
          inLanguage: htmlLang,
          ...(sector ? { about: { "@type": "Thing", name: sector } } : {}),
          // Where the machine-readable versions of this page live.
          // `distribution` is schema.org's own vocabulary for exactly that,
          // so a crawler that already parses the Dataset block gets pointed
          // at the markdown and the JSON without having to guess a URL
          // convention or read llms.txt.
          distribution: [
            {
              "@type": "DataDownload",
              encodingFormat: "text/markdown",
              contentUrl: `${BASE_URL}${markdownUrlFor(locale, ticker, markdownTab)}`,
            },
            {
              "@type": "DataDownload",
              encodingFormat: "application/json",
              contentUrl: `${BASE_URL}/api/tickers/${ticker}/indicators/`,
            },
          ],
        },
        {
          "@context": "https://schema.org",
          "@type": "BreadcrumbList",
          itemListElement: [
            { "@type": "ListItem", position: 1, name: "Sponda", item: `${BASE_URL}/${locale}` },
            { "@type": "ListItem", position: 2, name: ticker, item: `${BASE_URL}/${locale}/${ticker}` },
            ...(tabDisplayName ? [{
              "@type": "ListItem",
              position: 3,
              name: tabDisplayName,
              item: url,
            }] : []),
          ],
        },
      ]),
    },
  };

  return metadata;
}
