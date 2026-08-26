import { notFound } from "next/navigation";
import type { Metadata } from "next";

import { AiAccessArticle } from "./AiAccessArticle";
import { AI_ACCESS_INTRO, AI_ACCESS_TITLE } from "../../../lib/ai-access-copy";
import { isSupportedLocale, robotsForLocale } from "../../../lib/i18n-config";
import { SITE_BASE_URL } from "../../../lib/site-routes";

interface ForAiPageProps {
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: ForAiPageProps): Promise<Metadata> {
  const { locale } = await params;
  const url = `${SITE_BASE_URL}/${locale}/for-ai`;

  return {
    title: `${AI_ACCESS_TITLE} · Sponda`,
    description: AI_ACCESS_INTRO,
    robots: robotsForLocale(locale),
    alternates: {
      canonical: url,
      types: { "text/markdown": `${url}.md` },
    },
  };
}

export default async function ForAiPage({ params }: ForAiPageProps) {
  const { locale } = await params;
  if (!isSupportedLocale(locale)) notFound();

  return <AiAccessArticle />;
}
