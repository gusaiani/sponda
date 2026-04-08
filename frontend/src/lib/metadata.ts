import type { Metadata } from "next";
import { SUPPORTED_LOCALES, LOCALE_TO_OG_LOCALE, LOCALE_TO_HTML_LANG, type SupportedLocale } from "./i18n-config";
import { tabSlugForLocale, type TabKey } from "../utils/tabs";

const BASE_URL = "https://sponda.capital";

interface TickerInfo {
  name: string;
  sector: string;
}

async function fetchTickerInfo(ticker: string): Promise<TickerInfo | null> {
  const djangoUrl = process.env.DJANGO_API_URL || "http://localhost:8710";
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
  comparar: "compare", compare: "compare", comparer: "compare", vergleich: "compare",
};

/** Localized tab display names for breadcrumbs. */
const TAB_DISPLAY: Record<string, Record<string, string>> = {
  pt: { graficos: "Gráficos", fundamentos: "Fundamentos", comparar: "Comparar" },
  en: { charts: "Charts", fundamentals: "Fundamentals", compare: "Compare" },
  es: { graficos: "Gráficos", fundamentos: "Fundamentos", comparar: "Comparar" },
  zh: { charts: "图表", fundamentals: "基本面", compare: "对比" },
  fr: { graphiques: "Graphiques", fondamentaux: "Fondamentaux", comparer: "Comparer" },
  de: { diagramme: "Diagramme", fundamentaldaten: "Fundamentaldaten", vergleich: "Vergleich" },
};

/** Locale-specific title suffix. */
const TITLE_SUFFIX: Record<string, string> = {
  pt: "Indicadores Fundamentalistas",
  en: "Fundamental Indicators",
  es: "Indicadores Fundamentales",
  zh: "基本面指标",
  fr: "Indicateurs Fondamentaux",
  de: "Fundamentalkennzahlen",
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
  }
}

/** Locale-specific keywords. */
const KEYWORDS: Record<string, string[]> = {
  pt: ["PE10", "PFCF10", "PEG", "CAGR", "análise fundamentalista", "ações brasileiras", "B3"],
  en: ["PE10", "PFCF10", "PEG", "CAGR", "fundamental analysis", "stock market", "value investing"],
  es: ["PE10", "PFCF10", "PEG", "CAGR", "análisis fundamental", "acciones brasileñas", "inversión en valor"],
  zh: ["PE10", "PFCF10", "PEG", "CAGR", "基本面分析", "巴西股票", "价值投资"],
  fr: ["PE10", "PFCF10", "PEG", "CAGR", "analyse fondamentale", "actions brésiliennes", "investissement valeur"],
  de: ["PE10", "PFCF10", "PEG", "CAGR", "Fundamentalanalyse", "brasilianische Aktien", "Value-Investing"],
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
    },
    openGraph: {
      title,
      description,
      url,
      images: [{ url: `${BASE_URL}/images/sponda-og.jpg`, width: 1200, height: 630 }],
      locale: ogLocale,
      siteName: "Sponda",
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: [`${BASE_URL}/images/sponda-og.jpg`],
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
