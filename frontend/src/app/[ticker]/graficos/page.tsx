import { notFound } from "next/navigation";
import { TickerPageClient } from "../ticker-client";
import { fetchQuoteServer } from "../fetch-quote-server";

interface TickerGraficosPageProps {
  params: Promise<{ ticker: string }>;
}

export default async function TickerGraficosPage({ params }: TickerGraficosPageProps) {
  const { ticker } = await params;
  const upperTicker = ticker.toUpperCase();
  const result = await fetchQuoteServer(upperTicker);

  if (result.error === "not-found") {
    notFound();
  }

  return <TickerPageClient initialData={result.data} />;
}
