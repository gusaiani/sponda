export type TabKey = "metrics" | "charts" | "fundamentals" | "compare";

/** Locale-indexed tab URL slugs (no leading slash). */
const TAB_SLUGS: Record<string, Record<TabKey, string>> = {
  pt: { metrics: "", charts: "graficos", fundamentals: "fundamentos", compare: "comparar" },
  en: { metrics: "", charts: "charts", fundamentals: "fundamentals", compare: "compare" },
  es: { metrics: "", charts: "graficos", fundamentals: "fundamentos", compare: "comparar" },
  zh: { metrics: "", charts: "charts", fundamentals: "fundamentals", compare: "compare" },
  fr: { metrics: "", charts: "graphiques", fundamentals: "fondamentaux", compare: "comparer" },
  de: { metrics: "", charts: "diagramme", fundamentals: "fundamentaldaten", compare: "vergleich" },
};

/** Reverse mapping: slug → TabKey (accepts all locale slugs). */
const SLUG_TO_TAB: Record<string, TabKey> = {
  graficos: "charts",
  charts: "charts",
  graphiques: "charts",
  diagramme: "charts",
  fundamentos: "fundamentals",
  fundamentals: "fundamentals",
  fondamentaux: "fundamentals",
  fundamentaldaten: "fundamentals",
  comparar: "compare",
  compare: "compare",
  comparer: "compare",
  vergleich: "compare",
};

/** Legacy Portuguese labels (used by some tests). */
export const TAB_LABELS: Record<TabKey, string> = {
  metrics: "Indicadores",
  fundamentals: "Fundamentos",
  compare: "Comparar",
  charts: "Gráficos",
};

/** Return the URL slug for a tab in a given locale (e.g. "graficos" for pt/charts). */
export function tabSlugForLocale(locale: string, tab: TabKey): string {
  const slugs = TAB_SLUGS[locale] ?? TAB_SLUGS.en;
  return slugs[tab];
}

/** Resolve a pathname to a TabKey. Handles both locale-prefixed and bare paths. */
export function resolveTab(pathname: string): TabKey {
  const segments = pathname.split("/").filter(Boolean);
  // Last non-empty segment is the potential tab slug
  const lastSegment = segments[segments.length - 1] ?? "";
  return SLUG_TO_TAB[lastSegment] ?? "metrics";
}

/** Build a locale-prefixed tab path: /en/PETR4/fundamentals */
export function buildTabPath(locale: string, ticker: string, tab: TabKey): string {
  const slug = tabSlugForLocale(locale, tab);
  return slug ? `/${locale}/${ticker}/${slug}` : `/${locale}/${ticker}`;
}

/** Translate a tab slug from one locale to another.
 * e.g. translateTabSlug("fundamentos", "en") → "fundamentals" */
export function translateTabSlug(slug: string, targetLocale: string): string {
  const tab = SLUG_TO_TAB[slug];
  if (!tab) return slug;
  return tabSlugForLocale(targetLocale, tab) || slug;
}
