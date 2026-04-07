import type { Metadata } from "next";
import { generateTickerMetadata } from "../../../lib/metadata";
import type { SupportedLocale } from "../../../lib/i18n-config";

interface TickerLayoutProps {
  children: React.ReactNode;
  params: Promise<{ locale: string; ticker: string }>;
}

export async function generateMetadata({ params }: TickerLayoutProps): Promise<Metadata> {
  const { locale, ticker } = await params;
  return generateTickerMetadata(ticker.toUpperCase(), locale as SupportedLocale);
}

export default async function TickerLayout({ children, params }: TickerLayoutProps) {
  const { locale, ticker } = await params;
  const upperTicker = ticker.toUpperCase();

  const metadata = await generateTickerMetadata(upperTicker, locale as SupportedLocale);
  const structuredData = metadata.other?.["structured-data"];
  const jsonLdSchemas = structuredData ? JSON.parse(structuredData as string) : [];

  return (
    <>
      {jsonLdSchemas.map((schema: Record<string, unknown>, index: number) => (
        <script
          key={index}
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
        />
      ))}
      {children}
    </>
  );
}
