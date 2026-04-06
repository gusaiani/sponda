import type { Metadata } from "next";
import Script from "next/script";
import { Providers } from "./providers";
import { LayoutShell } from "./layout-shell";
import "./globals.css";

export const metadata: Metadata = {
  title: "Sponda · Para investidores em valor",
  description:
    "Indicadores fundamentalistas de empresas brasileiras para investidores em valor. P/L ajustado pela inflação (Shiller PE), P/FCL, PEG, CAGR, alavancagem e mais.",
  keywords:
    "ações brasileiras, indicadores fundamentalistas, P/L Shiller, PE10, CAPE, preço/lucro, investimento em valor, B3, bolsa de valores, análise fundamentalista",
  authors: [{ name: "Poema Parceria de Investimentos", url: "https://poe.ma" }],
  robots: "index, follow",
  metadataBase: new URL("https://sponda.capital"),
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    siteName: "Sponda",
    title: "Sponda · Para investidores em valor",
    description:
      "Indicadores fundamentalistas de empresas brasileiras para investidores em valor. P/L ajustado pela inflação, P/FCL, PEG, CAGR, alavancagem e mais.",
    url: "/",
    images: [{ url: "/images/sponda-og.jpg", width: 1200, height: 630 }],
    locale: "pt_BR",
  },
  twitter: {
    card: "summary_large_image",
    title: "Sponda · Para investidores em valor",
    description:
      "Indicadores fundamentalistas de empresas brasileiras para investidores em valor.",
    images: ["/images/sponda-og.jpg"],
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <head>
        <link rel="icon" type="image/svg+xml" href={process.env.NODE_ENV === "development" ? "/favicon-dev.svg" : "/favicon.svg"} />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Source+Code+Pro:wght@300;400&display=swap"
          rel="stylesheet"
        />
        <link rel="preload" href="/fonts/Satoshi-Medium.woff2" as="font" type="font/woff2" crossOrigin="anonymous" />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify({
              "@context": "https://schema.org",
              "@type": "WebApplication",
              name: "Sponda",
              url: "https://sponda.capital",
              description:
                "Indicadores fundamentalistas de empresas brasileiras para investidores em valor. P/L ajustado pela inflação (Shiller PE), P/FCL, PEG, CAGR e alavancagem.",
              applicationCategory: "FinanceApplication",
              operatingSystem: "Web",
              offers: { "@type": "Offer", price: "0", priceCurrency: "BRL" },
              creator: {
                "@type": "Organization",
                name: "Poema Parceria de Investimentos",
                url: "https://poe.ma",
              },
              inLanguage: "pt-BR",
            }),
          }}
        />
      </head>
      <body style={{ margin: 0 }}>
        <Providers>
          <LayoutShell>{children}</LayoutShell>
        </Providers>
        <Script
          id="posthog"
          strategy="afterInteractive"
          dangerouslySetInnerHTML={{
            __html: `!function(t,e){var o,n,p,r;e.__SV||(window.posthog=e,e._i=[],e.init=function(i,s,a){function g(t,e){var o=e.split(".");2==o.length&&(t=t[o[0]],e=o[1]),t[e]=function(){t.push([e].concat(Array.prototype.slice.call(arguments,0)))}}(p=t.createElement("script")).type="text/javascript",p.crossOrigin="anonymous",p.async=!0,p.src=s.api_host.replace(".i.posthog.com","-assets.i.posthog.com")+"/static/array.js",(r=t.getElementsByTagName("script")[0]).parentNode.insertBefore(p,r);var u=e;for(void 0!==a?u=e[a]=[]:a="posthog",u.people=u.people||[],u.toString=function(t){var e="posthog";return"posthog"!==a&&(e+="."+a),t||(e+=" (stub)"),e},u.people.toString=function(){return u.toString(1)+".people (stub)"},o="init capture register register_once register_for_session unregister unregister_for_session getFeatureFlag getFeatureFlagPayload isFeatureEnabled reloadFeatureFlags updateEarlyAccessFeatureEnrollment getEarlyAccessFeatures on onFeatureFlags onSessionId getSurveys getActiveMatchingSurveys renderSurvey canRenderSurvey getNextSurveyStep identify setPersonProperties group resetGroups setPersonPropertiesForFlags resetPersonPropertiesForFlags setGroupPropertiesForFlags resetGroupPropertiesForFlags reset get_distinct_id getGroups get_session_id get_session_replay_url alias set_config startSessionRecording stopSessionRecording sessionRecordingStarted captureException loadToolbar get_property getSessionProperty createPersonProfile opt_in_capturing opt_out_capturing has_opted_in_capturing has_opted_out_capturing clear_opt_in_out_capturing debug".split(" "),n=0;n<o.length;n++)g(u,o[n]);e._i.push([i,s,a])},e.__SV=1)}(document,window.posthog||[]);posthog.init('phc_wc1GnInP3s6Ff3H9DuG7fLogVKNwBJkMATmvI7CnGq6',{api_host:'https://us.i.posthog.com',person_profiles:'identified_only'});`,
          }}
        />
      </body>
    </html>
  );
}
