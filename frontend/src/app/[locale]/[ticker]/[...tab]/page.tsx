import { notFound } from "next/navigation";
import { TickerPageClient } from "../ticker-client";
import { fetchQuoteServer } from "../fetch-quote-server";
import { generateTickerMetadata } from "../../../../lib/metadata";
import { resolveTab, tabSlugForLocale } from "../../../../utils/tabs";
import type { SupportedLocale } from "../../../../lib/i18n-config";
import type { Metadata } from "next";

interface TabPageProps {
  params: Promise<{ locale: string; ticker: string; tab: string[] }>;
}

export async function generateMetadata({ params }: TabPageProps): Promise<Metadata> {
  const { locale, ticker, tab } = await params;
  const tabSlug = tab?.[0];
  if (!tabSlug) return {};
  return generateTickerMetadata(ticker.toUpperCase(), locale as SupportedLocale, tabSlug);
}

export default async function TabPage({ params }: TabPageProps) {
  const { locale, ticker, tab } = await params;
  const tabSlug = tab?.[0];

  if (!tabSlug) {
    notFound();
  }

  // Validate the tab slug is recognized
  const resolvedTab = resolveTab(`/${locale}/${ticker}/${tabSlug}`);
  if (resolvedTab === "metrics") {
    // "metrics" means unrecognized slug — the tab slug was invalid
    notFound();
  }

  // Validate the tab slug matches the current locale
  const expectedSlug = tabSlugForLocale(locale, resolvedTab);
  if (tabSlug !== expectedSlug) {
    // Wrong locale slug — middleware should have redirected, but just in case
    notFound();
  }

  const upperTicker = ticker.toUpperCase();
  const result = await fetchQuoteServer(upperTicker);

  if (result.error === "not-found") {
    notFound();
  }

  return <TickerPageClient initialData={result.data} />;
}
