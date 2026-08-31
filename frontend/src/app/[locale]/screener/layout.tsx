import type { Metadata } from "next";
import { generateScreenerMetadata } from "../../../lib/metadata";
import { isSupportedLocale } from "../../../lib/i18n-config";

interface ScreenerLayoutProps {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}

/**
 * The screener page is a client component and cannot export metadata of
 * its own; this layout gives it a title, description and canonical URL so
 * it stops inheriting the home page's.
 */
export async function generateMetadata({ params }: ScreenerLayoutProps): Promise<Metadata> {
  const { locale } = await params;
  if (!isSupportedLocale(locale)) return {};
  return generateScreenerMetadata(locale);
}

export default function ScreenerLayout({ children }: ScreenerLayoutProps) {
  return children;
}
