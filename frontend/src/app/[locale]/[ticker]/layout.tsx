import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { generateTickerMetadata } from "../../../lib/metadata";
import { isSupportedLocale, type SupportedLocale } from "../../../lib/i18n-config";

interface TickerLayoutProps {
  children: React.ReactNode;
  params: Promise<{ locale: string; ticker: string }>;
}

/**
 * An unsupported locale segment is a 404, the same answer the locale
 * layout below this one already gives.
 *
 * The middleware validates the segment, but its matcher skips any path
 * containing a dot, so a scanner probing `/wp-admin/install.php` or
 * `/wp-login.php` lands here directly. Before this check the layout cast
 * `wp-admin` to SupportedLocale, and the resulting undefined lookup was
 * the loudest error in Sentry: 5,791 crashes in twenty days, each one
 * having first spent a Django round trip on the ticker `install.php`.
 */
function requireSupportedLocale(locale: string): SupportedLocale {
  if (!isSupportedLocale(locale)) {
    notFound();
  }
  return locale;
}

export async function generateMetadata({ params }: TickerLayoutProps): Promise<Metadata> {
  const { locale, ticker } = await params;
  return generateTickerMetadata(ticker.toUpperCase(), requireSupportedLocale(locale));
}

export default async function TickerLayout({ children, params }: TickerLayoutProps) {
  const { locale, ticker } = await params;
  const supportedLocale = requireSupportedLocale(locale);
  const upperTicker = ticker.toUpperCase();

  const metadata = await generateTickerMetadata(upperTicker, supportedLocale);
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
