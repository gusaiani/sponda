import type { Metadata } from "next";
import { INDEXABLE_LOCALES, LOCALE_TO_OG_LOCALE, LOCALE_TO_HTML_LANG, type SupportedLocale } from "./i18n-config";
import { tabSlugForLocale, type TabKey } from "../utils/tabs";
import { djangoApiBaseUrl } from "./django-api";
import { markdownUrlFor } from "./markdown-routes";
import { ogImageUrlForTicker } from "./og-card";

const BASE_URL = "https://sponda.capital";

/**
 * Longest <title> that survives a Google result intact. Google truncates by
 * pixel width, which works out to roughly this many characters; anything
 * longer is cut mid-word, usually through the company name.
 */
export const MAX_TITLE_LENGTH = 60;

const OG_IMAGE_WIDTH = 1200;
const OG_IMAGE_HEIGHT = 630;
const OG_IMAGE_MIME_TYPE = "image/jpeg";
const TICKER_OG_IMAGE_MIME_TYPE = "image/png";
const OG_IMAGE_ALT_TEXT = "Sponda · fundamental indicators for value investors";

/**
 * Path to the OG image for a given locale.
 *
 * The Portuguese image uses the Portuguese tagline; every other locale
 * falls back to the English image. Only two JPEGs are maintained today
 * because most crawlers only cache one OG image per URL and localizing
 * the tagline further isn't worth the asset churn yet.
 *
 * The `-v2` suffix is a deliberate cache bust. X's card pipeline kept
 * re-fetching the unsuffixed URLs (~100x/day, 7x more often than it crawled
 * the pages themselves) while rendering every card without an image, which
 * is the signature of an image-cache entry stuck in a failed state. Since
 * there is no way to purge X's cache, a new URL is the only lever. The
 * unsuffixed files stay in place so previews already cached by other
 * networks keep resolving.
 */
export function getOgImageUrl(locale: string): string {
  return locale === "pt"
    ? "/images/sponda-og-v2.jpg"
    : "/images/sponda-og-en-v2.jpg";
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

/** Localized tab display names for titles and breadcrumbs. */
const TAB_DISPLAY: Record<string, Record<string, string>> = {
  pt: { graficos: "Gráficos", fundamentos: "Fundamentos", comparar: "Comparar", sponds: "Sponds" },
  en: { charts: "Charts", fundamentals: "Fundamentals", compare: "Compare", sponds: "Sponds" },
  es: { graficos: "Gráficos", fundamentos: "Fundamentos", comparar: "Comparar", sponds: "Sponds" },
  zh: { charts: "图表", fundamentals: "基本面", compare: "对比", sponds: "Sponds" },
  fr: { graphiques: "Graphiques", fondamentaux: "Fondamentaux", comparer: "Comparer", sponds: "Sponds" },
  de: { diagramme: "Diagramme", fundamentaldaten: "Fundamentaldaten", vergleich: "Vergleich", sponds: "Sponds" },
  it: { grafici: "Grafici", fondamentali: "Fondamentali", confronta: "Confronta", sponds: "Sponds" },
};

/**
 * What each tab shows, per locale. The company root describes the
 * indicators; a tab that repeats that description is a duplicate to a
 * search engine, and four identical pages per company across 18,000
 * companies is a site-wide duplicate-content signal.
 */
type TabDescriptionBuilder = (name: string, ticker: string) => string;

const TAB_DESCRIPTIONS: Record<SupportedLocale, Record<TabKey, TabDescriptionBuilder>> = {
  pt: {
    metrics: (name, ticker) => `Indicadores fundamentalistas de ${name} (${ticker}): P/L ajustado pela inflação (PE10), P/FCL10, PEG, CAGR e alavancagem. Dados atualizados.`,
    charts: (name, ticker) => `Gráficos de ${name} (${ticker}): PE10, P/FCL10 e histórico de preço, ajustados pela inflação.`,
    fundamentals: (name, ticker) => `Fundamentos de ${name} (${ticker}): receita, lucro, fluxo de caixa livre, dívida e patrimônio por ano, ajustados pela inflação.`,
    compare: (name, ticker) => `Compare ${name} (${ticker}) com pares do setor em PE10, P/FCL10, PEG, alavancagem e liquidez.`,
    sponds: (name, ticker) => `Sponds sobre ${name} (${ticker}): o que investidores em valor estão dizendo.`,
  },
  en: {
    metrics: (name, ticker) => `Fundamental indicators for ${name} (${ticker}): inflation-adjusted P/E (PE10), P/FCF10, PEG, CAGR and leverage. Updated data.`,
    charts: (name, ticker) => `Charts for ${name} (${ticker}): PE10, P/FCF10 and price history, inflation-adjusted.`,
    fundamentals: (name, ticker) => `Fundamentals of ${name} (${ticker}): revenue, earnings, free cash flow, debt and equity by year, inflation-adjusted.`,
    compare: (name, ticker) => `Compare ${name} (${ticker}) with sector peers on PE10, P/FCF10, PEG, leverage and liquidity.`,
    sponds: (name, ticker) => `Sponds about ${name} (${ticker}): what value investors are saying.`,
  },
  es: {
    metrics: (name, ticker) => `Indicadores fundamentales de ${name} (${ticker}): P/E ajustado por inflación (PE10), P/FCF10, PEG, CAGR y apalancamiento. Datos actualizados.`,
    charts: (name, ticker) => `Gráficos de ${name} (${ticker}): PE10, P/FCF10 e historial de precio, ajustados por inflación.`,
    fundamentals: (name, ticker) => `Fundamentos de ${name} (${ticker}): ingresos, beneficios, flujo de caja libre, deuda y patrimonio por año, ajustados por inflación.`,
    compare: (name, ticker) => `Compara ${name} (${ticker}) con sus pares del sector en PE10, P/FCF10, PEG, apalancamiento y liquidez.`,
    sponds: (name, ticker) => `Sponds sobre ${name} (${ticker}): lo que dicen los inversores en valor.`,
  },
  zh: {
    metrics: (name, ticker) => `${name} (${ticker}) 基本面指标：通胀调整市盈率 (PE10)、P/FCF10、PEG、CAGR 及杠杆率。数据持续更新。`,
    charts: (name, ticker) => `${name} (${ticker}) 图表：PE10、P/FCF10 及通胀调整后的价格历史。`,
    fundamentals: (name, ticker) => `${name} (${ticker}) 基本面：逐年营收、利润、自由现金流、债务与股东权益，经通胀调整。`,
    compare: (name, ticker) => `将 ${name} (${ticker}) 与同行业公司在 PE10、P/FCF10、PEG、杠杆率和流动性上进行对比。`,
    sponds: (name, ticker) => `关于 ${name} (${ticker}) 的 Sponds：价值投资者的看法。`,
  },
  fr: {
    metrics: (name, ticker) => `Indicateurs fondamentaux de ${name} (${ticker}) : P/E ajusté de l'inflation (PE10), P/FCF10, PEG, CAGR et endettement. Données actualisées.`,
    charts: (name, ticker) => `Graphiques de ${name} (${ticker}) : PE10, P/FCF10 et historique du cours, ajustés de l'inflation.`,
    fundamentals: (name, ticker) => `Fondamentaux de ${name} (${ticker}) : chiffre d'affaires, bénéfices, flux de trésorerie disponible, dette et capitaux propres par année, ajustés de l'inflation.`,
    compare: (name, ticker) => `Comparez ${name} (${ticker}) à ses pairs sectoriels sur le PE10, le P/FCF10, le PEG, l'endettement et la liquidité.`,
    sponds: (name, ticker) => `Sponds sur ${name} (${ticker}) : ce qu'en disent les investisseurs value.`,
  },
  de: {
    metrics: (name, ticker) => `Fundamentalkennzahlen für ${name} (${ticker}): inflationsbereinigtes KGV (PE10), P/FCF10, PEG, CAGR und Verschuldung. Aktuelle Daten.`,
    charts: (name, ticker) => `Diagramme zu ${name} (${ticker}): PE10, P/FCF10 und Kursverlauf, inflationsbereinigt.`,
    fundamentals: (name, ticker) => `Fundamentaldaten zu ${name} (${ticker}): Umsatz, Gewinn, freier Cashflow, Schulden und Eigenkapital je Jahr, inflationsbereinigt.`,
    compare: (name, ticker) => `Vergleichen Sie ${name} (${ticker}) mit Branchenkollegen nach PE10, P/FCF10, PEG, Verschuldung und Liquidität.`,
    sponds: (name, ticker) => `Sponds zu ${name} (${ticker}): was Value-Investoren sagen.`,
  },
  it: {
    metrics: (name, ticker) => `Indicatori fondamentali di ${name} (${ticker}): P/E corretto per l'inflazione (PE10), P/FCF10, PEG, CAGR e leva finanziaria. Dati aggiornati.`,
    charts: (name, ticker) => `Grafici di ${name} (${ticker}): PE10, P/FCF10 e storico dei prezzi, corretti per l'inflazione.`,
    fundamentals: (name, ticker) => `Fondamentali di ${name} (${ticker}): ricavi, utili, flusso di cassa libero, debito e patrimonio netto per anno, corretti per l'inflazione.`,
    compare: (name, ticker) => `Confronta ${name} (${ticker}) con i concorrenti del settore su PE10, P/FCF10, PEG, leva finanziaria e liquidità.`,
    sponds: (name, ticker) => `Sponds su ${name} (${ticker}): cosa dicono gli investitori di valore.`,
  },
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

/** Locale- and tab-specific description. */
function buildDescription(locale: SupportedLocale, ticker: string, companyName: string, tab: TabKey): string {
  const name = companyName || ticker;
  return TAB_DESCRIPTIONS[locale][tab](name, ticker);
}

/**
 * The first candidate that fits the SERP, most informative first. Every
 * candidate keeps the ticker and the site name; what gets dropped is the
 * generic suffix, then the company name, in that order.
 */
function fitTitle(candidates: string[]): string {
  return candidates.find((candidate) => candidate.length <= MAX_TITLE_LENGTH) ?? candidates[candidates.length - 1];
}

function buildTitle(ticker: string, companyName: string, suffix: string, tabDisplayName?: string): string {
  const subject = companyName ? `${companyName} (${ticker})` : ticker;
  if (tabDisplayName) {
    return fitTitle([
      `${subject} · ${tabDisplayName} · Sponda`,
      `${ticker} · ${tabDisplayName} · Sponda`,
    ]);
  }
  return fitTitle([
    `${subject} · ${suffix} · Sponda`,
    `${subject} · Sponda`,
    `${ticker} · ${suffix} · Sponda`,
  ]);
}

/** Joins the localized "Fundamental Indicators" with the company in the Dataset name. */
const DATASET_NAME_SEPARATOR: Record<SupportedLocale, string> = {
  pt: " · ", en: " · ", es: " · ", zh: "：", fr: " de ", de: " für ", it: " · ",
};

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

  // Build alternates for the indexable locales only: a noindex locale must
  // not be advertised as a crawlable alternate.
  const alternateLanguages: Record<string, string> = {};
  for (const altLocale of INDEXABLE_LOCALES) {
    let altTabSlug: string | undefined;
    if (tabSlug) {
      const tabKey = SLUG_TO_TAB[tabSlug];
      altTabSlug = tabKey ? tabSlugForLocale(altLocale, tabKey) : tabSlug;
    }
    const altPath = altTabSlug
      ? `${BASE_URL}/${altLocale}/${ticker}/${altTabSlug}`
      : `${BASE_URL}/${altLocale}/${ticker}`;
    const langKey = altLocale === "pt" ? "pt-BR" : altLocale;
    alternateLanguages[langKey] = altPath;
  }
  alternateLanguages["x-default"] = alternateLanguages["en"];

  // Title and breadcrumb tab name
  const tabDisplayName = tabSlug
    ? (TAB_DISPLAY[locale]?.[tabSlug] || tabSlug)
    : undefined;

  // Locale- and tab-specific title and description
  const suffix = TITLE_SUFFIX[locale];
  const title = buildTitle(ticker, companyName, suffix, tabDisplayName);
  const description = buildDescription(locale, ticker, companyName, markdownTab);

  const ogLocale = LOCALE_TO_OG_LOCALE[locale];
  const htmlLang = LOCALE_TO_HTML_LANG[locale];
  const tickerOgImage = buildTickerOgImageDescriptor(locale, ticker, companyName);

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
          name: `${suffix}${DATASET_NAME_SEPARATOR[locale]}${companyName || ticker} (${ticker})`,
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

/** Title and description of the screener, per locale. */
const SCREENER_META: Record<SupportedLocale, { title: string; description: string }> = {
  pt: {
    title: "Filtro de Ações · Sponda",
    description: "Filtre empresas listadas no mundo todo por P/L ajustado pela inflação (PE10), P/FCL10, PEG, alavancagem e liquidez. Por setor e país.",
  },
  en: {
    title: "Stock Screener · Sponda",
    description: "Screen listed companies worldwide by inflation-adjusted P/E (PE10), P/FCF10, PEG, leverage and liquidity ratios. Filter by sector and country.",
  },
  es: {
    title: "Filtro de Acciones · Sponda",
    description: "Filtra empresas cotizadas de todo el mundo por P/E ajustado por inflación (PE10), P/FCF10, PEG, apalancamiento y liquidez. Por sector y país.",
  },
  zh: {
    title: "股票筛选器 · Sponda",
    description: "按通胀调整市盈率 (PE10)、P/FCF10、PEG、杠杆率和流动性筛选全球上市公司，可按行业和国家过滤。",
  },
  fr: {
    title: "Filtre d'actions · Sponda",
    description: "Filtrez les sociétés cotées du monde entier par P/E ajusté de l'inflation (PE10), P/FCF10, PEG, endettement et liquidité. Par secteur et pays.",
  },
  de: {
    title: "Aktien-Screener · Sponda",
    description: "Filtern Sie börsennotierte Unternehmen weltweit nach inflationsbereinigtem KGV (PE10), P/FCF10, PEG, Verschuldung und Liquidität. Nach Branche und Land.",
  },
  it: {
    title: "Screener Azioni · Sponda",
    description: "Filtra le società quotate di tutto il mondo per P/E corretto per l'inflazione (PE10), P/FCF10, PEG, leva finanziaria e liquidità. Per settore e paese.",
  },
};

/**
 * Metadata for `/<locale>/screener`.
 *
 * The screener is a client component, so without this it inherited the
 * locale layout's metadata wholesale: the home page's title, description
 * and, worst of all, `canonical: /<locale>`. A page whose canonical points
 * elsewhere is one a search engine will not index, and its sitemap hreflang
 * entries contradict the page itself.
 */
export function generateScreenerMetadata(locale: SupportedLocale): Metadata {
  const { title, description } = SCREENER_META[locale];
  const url = `${BASE_URL}/${locale}/screener`;

  const alternateLanguages: Record<string, string> = {};
  for (const altLocale of INDEXABLE_LOCALES) {
    const langKey = altLocale === "pt" ? "pt-BR" : altLocale;
    alternateLanguages[langKey] = `${BASE_URL}/${altLocale}/screener`;
  }
  alternateLanguages["x-default"] = `${BASE_URL}/en/screener`;

  const ogImage = buildOgImageDescriptor(locale);

  return {
    title,
    description,
    alternates: {
      canonical: url,
      languages: alternateLanguages,
    },
    openGraph: {
      type: "website",
      siteName: "Sponda",
      title,
      description,
      url,
      images: [ogImage],
      locale: LOCALE_TO_OG_LOCALE[locale],
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: [ogImage.url],
    },
  };
}
