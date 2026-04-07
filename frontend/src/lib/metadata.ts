import type { Metadata } from "next";
import { LOCALE_TO_OG_LOCALE, LOCALE_TO_HTML_LANG, type SupportedLocale } from "./i18n-config";
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
  graficos: "charts", charts: "charts",
  fundamentos: "fundamentals", fundamentals: "fundamentals",
  comparar: "compare", compare: "compare",
};

/** Localized tab display names for breadcrumbs. */
const TAB_DISPLAY: Record<string, Record<string, string>> = {
  pt: { graficos: "Gráficos", fundamentos: "Fundamentos", comparar: "Comparar" },
  en: { charts: "Charts", fundamentals: "Fundamentals", compare: "Compare" },
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

  // Build alternate locale path
  const altLocale: SupportedLocale = locale === "pt" ? "en" : "pt";
  let altTabSlug: string | undefined;
  if (tabSlug) {
    const tabKey = SLUG_TO_TAB[tabSlug];
    altTabSlug = tabKey ? tabSlugForLocale(altLocale, tabKey) : tabSlug;
  }
  const altPath = altTabSlug
    ? `${altLocale}/${ticker}/${altTabSlug}`
    : `${altLocale}/${ticker}`;

  // Locale-specific title and description
  const title = locale === "pt"
    ? (companyName
      ? `${companyName} (${ticker}) · Indicadores Fundamentalistas · Sponda`
      : `${ticker} · Indicadores Fundamentalistas · Sponda`)
    : (companyName
      ? `${companyName} (${ticker}) · Fundamental Indicators · Sponda`
      : `${ticker} · Fundamental Indicators · Sponda`);

  const description = locale === "pt"
    ? (companyName
      ? `Indicadores fundamentalistas de ${companyName} (${ticker}): P/L ajustado pela inflação (PE10), P/FCL10, PEG, CAGR e alavancagem. Dados atualizados.`
      : `Indicadores fundamentalistas de ${ticker}: P/L ajustado pela inflação, P/FCL, PEG, CAGR e alavancagem.`)
    : (companyName
      ? `Fundamental indicators for ${companyName} (${ticker}): inflation-adjusted P/E (PE10), P/FCF10, PEG, CAGR and leverage. Updated data.`
      : `Fundamental indicators for ${ticker}: inflation-adjusted P/E, P/FCF, PEG, CAGR and leverage.`);

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
      languages: {
        "pt-BR": `${BASE_URL}/${locale === "pt" ? localePath : altPath.replace(/^en/, "pt")}`,
        en: `${BASE_URL}/${locale === "en" ? localePath : altPath.replace(/^pt/, "en")}`,
        "x-default": `${BASE_URL}/en/${ticker}${altTabSlug && locale === "pt" ? `/${altTabSlug}` : (tabSlug && locale === "en" ? `/${tabSlug}` : "")}`,
      },
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
          name: locale === "pt"
            ? `Indicadores Fundamentalistas de ${companyName || ticker} (${ticker})`
            : `Fundamental Indicators for ${companyName || ticker} (${ticker})`,
          description,
          url,
          keywords: locale === "pt"
            ? [ticker, companyName || ticker, "PE10", "PFCF10", "PEG", "CAGR", "análise fundamentalista", "ações brasileiras", "B3"]
            : [ticker, companyName || ticker, "PE10", "PFCF10", "PEG", "CAGR", "fundamental analysis", "stock market", "value investing"],
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
