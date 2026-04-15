import type { Metadata } from "next";
import Script from "next/script";
import { notFound } from "next/navigation";
import { Providers } from "../providers";
import { LayoutShell } from "../layout-shell";
import { SUPPORTED_LOCALES, isSupportedLocale, LOCALE_TO_HTML_LANG, LOCALE_TO_OG_LOCALE } from "../../lib/i18n-config";
import { getOgImageUrl } from "../../lib/metadata";
import type { Locale } from "../../i18n/types";

const BASE_URL = "https://sponda.capital";

const META: Record<string, { title: string; description: string }> = {
  pt: {
    title: "Sponda · Para investidores em valor",
    description:
      "Indicadores fundamentalistas para investidores em valor. P/L ajustado pela inflação (Shiller PE), P/FCL, PEG, CAGR, alavancagem e mais.",
  },
  en: {
    title: "Sponda · For value investors",
    description:
      "Fundamental indicators for value investors. Inflation-adjusted P/E (Shiller PE), P/FCF, PEG, CAGR, leverage ratios and more.",
  },
  es: {
    title: "Sponda · Para inversores en valor",
    description:
      "Indicadores fundamentales para inversores en valor. P/E ajustado por inflación (Shiller PE), P/FCF, PEG, CAGR, apalancamiento y más.",
  },
  zh: {
    title: "Sponda · 价值投资者工具",
    description:
      "价值投资者基本面指标。通胀调整市盈率 (Shiller PE)、P/FCF、PEG、CAGR、杠杆率等。",
  },
  fr: {
    title: "Sponda · Pour investisseurs value",
    description:
      "Indicateurs fondamentaux pour investisseurs value. P/E ajusté de l'inflation (Shiller PE), P/FCF, PEG, CAGR, endettement et plus.",
  },
  de: {
    title: "Sponda · Für Value-Investoren",
    description:
      "Fundamentalkennzahlen für Value-Investoren. Inflationsbereinigtes KGV (Shiller PE), P/FCF, PEG, CAGR, Verschuldung und mehr.",
  },
  it: {
    title: "Sponda · Per investitori di valore",
    description:
      "Indicatori fondamentali per investitori di valore. P/E corretto per l'inflazione (Shiller PE), P/FCF, PEG, CAGR, leva finanziaria e altro.",
  },
};

interface LocaleLayoutProps {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: LocaleLayoutProps): Promise<Metadata> {
  const { locale } = await params;
  if (!isSupportedLocale(locale)) return {};

  const { title, description } = META[locale];
  const ogLocale = LOCALE_TO_OG_LOCALE[locale];

  const KEYWORDS: Record<string, string> = {
    pt: "análise fundamentalista, indicadores fundamentalistas, P/L Shiller, PE10, CAPE, preço/lucro, investimento em valor, mercado de ações, ações globais",
    en: "stock analysis, fundamental indicators, Shiller PE, PE10, CAPE, price/earnings, value investing, stock market, fundamental analysis",
    es: "análisis fundamental, indicadores fundamentales, Shiller PE, PE10, CAPE, precio/beneficio, inversión en valor, mercado de valores, acciones globales",
    zh: "基本面分析, 股票分析, Shiller PE, PE10, CAPE, 市盈率, 价值投资, 全球股票, 股票市场",
    fr: "analyse fondamentale, indicateurs fondamentaux, Shiller PE, PE10, CAPE, prix/bénéfice, investissement valeur, marché boursier, actions mondiales",
    de: "Fundamentalanalyse, Fundamentalkennzahlen, Shiller PE, PE10, CAPE, KGV, Value-Investing, Aktienmarkt, globale Aktien",
    it: "analisi fondamentale, indicatori fondamentali, Shiller PE, PE10, CAPE, P/E, investimento di valore, mercato azionario, azioni globali",
  };

  // Build hreflang alternates for all supported locales
  const alternateLanguages: Record<string, string> = {};
  for (const loc of SUPPORTED_LOCALES) {
    const key = loc === "pt" ? "pt-BR" : loc;
    alternateLanguages[key] = `/${loc}`;
  }
  alternateLanguages["x-default"] = "/en";

  return {
    title,
    description,
    keywords: KEYWORDS[locale] || KEYWORDS.en,
    authors: [{ name: "Poema Parceria de Investimentos", url: "https://poe.ma" }],
    robots: "index, follow",
    metadataBase: new URL(BASE_URL),
    alternates: {
      canonical: `/${locale}`,
      languages: alternateLanguages,
    },
    openGraph: {
      type: "website",
      siteName: "Sponda",
      title,
      description,
      url: `/${locale}`,
      images: [{ url: `${BASE_URL}${getOgImageUrl(locale)}`, width: 1200, height: 630 }],
      locale: ogLocale,
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: [`${BASE_URL}${getOgImageUrl(locale)}`],
    },
  };
}

export default async function LocaleLayout({ children, params }: LocaleLayoutProps) {
  const { locale } = await params;
  if (!isSupportedLocale(locale)) {
    notFound();
  }

  const htmlLang = LOCALE_TO_HTML_LANG[locale];

  return (
    <Providers locale={locale as Locale}>
      <LayoutShell>
        {children}
      </LayoutShell>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify({
            "@context": "https://schema.org",
            "@type": "WebApplication",
            name: "Sponda",
            url: BASE_URL,
            description: META[locale].description,
            applicationCategory: "FinanceApplication",
            operatingSystem: "Web",
            offers: { "@type": "Offer", price: "0", priceCurrency: "USD" },
            creator: {
              "@type": "Organization",
              name: "Poema Parceria de Investimentos",
              url: "https://poe.ma",
            },
            inLanguage: htmlLang,
          }),
        }}
      />
      <Script
        id="posthog"
        strategy="afterInteractive"
        dangerouslySetInnerHTML={{
          __html: `!function(t,e){var o,n,p,r;e.__SV||(window.posthog=e,e._i=[],e.init=function(i,s,a){function g(t,e){var o=e.split(".");2==o.length&&(t=t[o[0]],e=o[1]),t[e]=function(){t.push([e].concat(Array.prototype.slice.call(arguments,0)))}}(p=t.createElement("script")).type="text/javascript",p.crossOrigin="anonymous",p.async=!0,p.src=s.api_host.replace(".i.posthog.com","-assets.i.posthog.com")+"/static/array.js",(r=t.getElementsByTagName("script")[0]).parentNode.insertBefore(p,r);var u=e;for(void 0!==a?u=e[a]=[]:a="posthog",u.people=u.people||[],u.toString=function(t){var e="posthog";return"posthog"!==a&&(e+="."+a),t||(e+=" (stub)"),e},u.people.toString=function(){return u.toString(1)+".people (stub)"},o="init capture register register_once register_for_session unregister unregister_for_session getFeatureFlag getFeatureFlagPayload isFeatureEnabled reloadFeatureFlags updateEarlyAccessFeatureEnrollment getEarlyAccessFeatures on onFeatureFlags onSessionId getSurveys getActiveMatchingSurveys renderSurvey canRenderSurvey getNextSurveyStep identify setPersonProperties group resetGroups setPersonPropertiesForFlags resetPersonPropertiesForFlags setGroupPropertiesForFlags resetGroupPropertiesForFlags reset get_distinct_id getGroups get_session_id get_session_replay_url alias set_config startSessionRecording stopSessionRecording sessionRecordingStarted captureException loadToolbar get_property getSessionProperty createPersonProfile opt_in_capturing opt_out_capturing has_opted_in_capturing has_opted_out_capturing clear_opt_in_out_capturing debug".split(" "),n=0;n<o.length;n++)g(u,o[n]);e._i.push([i,s,a])},e.__SV=1)}(document,window.posthog||[]);posthog.init('phc_wc1GnInP3s6Ff3H9DuG7fLogVKNwBJkMATmvI7CnGq6',{api_host:'https://us.i.posthog.com',person_profiles:'identified_only'});`,
        }}
      />
    </Providers>
  );
}
