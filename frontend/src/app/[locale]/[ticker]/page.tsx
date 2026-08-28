import { notFound } from "next/navigation";
import { TickerPageClient } from "./ticker-client";
import { fetchQuoteServer } from "./fetch-quote-server";
import { fetchPeersServer } from "./fetch-peers-server";

interface TickerPageProps {
  params: Promise<{ ticker: string }>;
}

export default async function TickerMetricsPage({ params }: TickerPageProps) {
  const { ticker } = await params;
  const upperTicker = ticker.toUpperCase();
  const [result, peers] = await Promise.all([
    fetchQuoteServer(upperTicker),
    fetchPeersServer(upperTicker),
  ]);

  if (result.error === "not-found") {
    notFound();
  }

  return <TickerPageClient initialData={result.data} initialPeers={peers} />;
}
