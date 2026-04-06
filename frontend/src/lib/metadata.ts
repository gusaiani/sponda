import type { Metadata } from "next";

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

export async function generateTickerMetadata(ticker: string, subPath?: string): Promise<Metadata> {
  const info = await fetchTickerInfo(ticker);
  const companyName = info?.name || "";
  const sector = info?.sector || "";

  const fullPath = subPath ? `${ticker}/${subPath}` : ticker;
  const url = `${BASE_URL}/${fullPath}`;
  const title = companyName
    ? `${companyName} (${ticker}) · Indicadores Fundamentalistas · Sponda`
    : `${ticker} · Indicadores Fundamentalistas · Sponda`;

  const description = companyName
    ? `Indicadores fundamentalistas de ${companyName} (${ticker}): P/L ajustado pela inflação (PE10), P/FCL10, PEG, CAGR e alavancagem. Dados atualizados.`
    : `Indicadores fundamentalistas de ${ticker}: P/L ajustado pela inflação, P/FCL, PEG, CAGR e alavancagem.`;

  const metadata: Metadata = {
    title,
    description,
    alternates: { canonical: url },
    openGraph: {
      title,
      description,
      url,
      images: [{ url: `${BASE_URL}/images/sponda-og.jpg`, width: 1200, height: 630 }],
      locale: "pt_BR",
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
          name: `Indicadores Fundamentalistas de ${companyName || ticker} (${ticker})`,
          description,
          url,
          keywords: [
            ticker, companyName || ticker, "PE10", "PFCF10", "PEG", "CAGR",
            "análise fundamentalista", "ações brasileiras", "B3",
          ],
          creator: { "@type": "Organization", name: "Sponda", url: BASE_URL },
          inLanguage: "pt-BR",
          ...(sector ? { about: { "@type": "Thing", name: sector } } : {}),
        },
        {
          "@context": "https://schema.org",
          "@type": "BreadcrumbList",
          itemListElement: [
            { "@type": "ListItem", position: 1, name: "Sponda", item: `${BASE_URL}/` },
            { "@type": "ListItem", position: 2, name: ticker, item: `${BASE_URL}/${ticker}` },
            ...(subPath ? [{
              "@type": "ListItem",
              position: 3,
              name: subPath === "graficos" ? "Gráficos" : subPath === "fundamentos" ? "Fundamentos" : "Comparar",
              item: url,
            }] : []),
          ],
        },
      ]),
    },
  };

  return metadata;
}
