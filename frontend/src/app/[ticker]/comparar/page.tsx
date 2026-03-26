import { notFound } from "next/navigation";
import { TickerPageClient } from "../ticker-client";
import { fetchQuoteServer } from "../fetch-quote-server";

interface TickerCompararPageProps {
  params: Promise<{ ticker: string }>;
}

export default async function TickerCompararPage({ params }: TickerCompararPageProps) {
  const { ticker } = await params;
  const upperTicker = ticker.toUpperCase();
  const result = await fetchQuoteServer(upperTicker);

  if (result.error === "not-found") {
    notFound();
  }

  return <TickerPageClient initialData={result.data} />;
}
