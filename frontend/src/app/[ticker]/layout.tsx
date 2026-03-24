import type { Metadata } from "next";
import { generateTickerMetadata } from "../../lib/metadata";

interface TickerLayoutProps {
  children: React.ReactNode;
  params: Promise<{ ticker: string }>;
}

export async function generateMetadata({ params }: TickerLayoutProps): Promise<Metadata> {
  const { ticker } = await params;
  return generateTickerMetadata(ticker.toUpperCase());
}

export default async function TickerLayout({ children, params }: TickerLayoutProps) {
  const { ticker } = await params;
  const upperTicker = ticker.toUpperCase();

  // Structured data JSON-LD (from metadata.other)
  const metadata = await generateTickerMetadata(upperTicker);
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
