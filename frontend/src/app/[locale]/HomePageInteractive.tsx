"use client";

import { HomepageGrid } from "../../components/HomepageGrid";
import { PopularCompanies } from "../../components/PopularCompanies";
import { ShareButtons } from "../../components/ShareButtons";

import { SeoArticle } from "./SeoArticle";
import type { Locale } from "../../i18n/types";

interface HomePageInteractiveProps {
  locale: Locale;
}

/** Client-only subtree of the home page. Wraps the existing components
 *  unchanged so the SSR shell can dehydrate React Query state into them
 *  without forcing a client-side fetch round-trip. */
export function HomePageInteractive({ locale }: HomePageInteractiveProps) {
  return (
    <div>
      <HomepageGrid />

      <PopularCompanies />

      {/* Hidden SEO article — provides crawlable text for search engines */}
      <SeoArticle locale={locale} />

      <ShareButtons />
    </div>
  );
}
