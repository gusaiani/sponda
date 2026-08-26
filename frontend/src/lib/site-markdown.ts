/**
 * The markdown twin of the pages that are not about one company: the home
 * page and the screener.
 *
 * The screener page doubles as the glossary. Every company page links to it
 * instead of repeating twenty indicator definitions across 23,000 documents,
 * and the definitions themselves come from Django's
 * `/api/assistant/indicators/`, which serves the same catalogue the MCP
 * tools are described from. One definition, three readers.
 */
import { djangoApiBaseUrl } from "./django-api";
import { escapeTableCell } from "./company-markdown";
import { SITE_BASE_URL } from "./site-routes";
import { ARTICLES } from "./site-copy";
import { translatorFor } from "../i18n/dictionaries";
import { DEFAULT_LOCALE, type SupportedLocale } from "./i18n-config";

/** The catalogue changes when the universe grows, which is rare. */
const CATALOGUE_REVALIDATE_SECONDS = 86400;

/** Companies named on the home page as worked examples. */
const EXAMPLE_TICKERS = ["PETR4", "VALE3", "AAPL"];

export interface IndicatorCatalogueEntry {
  key: string;
  name: string;
  definition: string;
  direction: string;
  note?: string;
}

export interface IndicatorCatalogue {
  indicators: IndicatorCatalogueEntry[];
  countries: string[];
  sectors: string[];
  unsupported_examples: string[];
}

export async function fetchIndicatorCatalogue(): Promise<IndicatorCatalogue | null> {
  try {
    const response = await fetch(`${djangoApiBaseUrl()}/api/assistant/indicators/`, {
      next: { revalidate: CATALOGUE_REVALIDATE_SECONDS },
    });
    if (!response.ok) return null;
    return (await response.json()) as IndicatorCatalogue;
  } catch {
    return null;
  }
}

function articleFor(locale: SupportedLocale) {
  return ARTICLES[locale] ?? ARTICLES[DEFAULT_LOCALE];
}

/** `lower_is_better` reads better as prose in a table cell. */
function directionLabel(direction: string): string {
  return direction.replace(/_/g, " ");
}

export function renderHomeMarkdown(locale: SupportedLocale): string {
  const translate = translatorFor(locale);
  const article = articleFor(locale);

  const blocks = [
    "# Sponda",
    `> ${translate("header.tagline")}`,
    translate("markdown.intro"),
    `[${translate("markdown.html_version")}](${SITE_BASE_URL}/${locale})`,
    `## ${article.title}`,
    ...article.sections.flatMap((section) => [`### ${section.heading}`, section.text]),
    `## ${translate("markdown.section_other_views")}`,
    [
      `- [${translate("markdown.definitions")}](${SITE_BASE_URL}/${locale}/screener.md)`,
      ...EXAMPLE_TICKERS.map(
        (ticker) => `- [${ticker}](${SITE_BASE_URL}/${locale}/${ticker}.md)`,
      ),
      `- [llms.txt](${SITE_BASE_URL}/llms.txt)`,
      `- [sitemap.xml](${SITE_BASE_URL}/sitemap.xml)`,
    ].join("\n"),
  ];

  return `${blocks.join("\n\n")}\n`;
}

export function renderScreenerMarkdown(
  locale: SupportedLocale,
  catalogue: IndicatorCatalogue | null,
): string {
  const translate = translatorFor(locale);

  const blocks = [
    `# ${translate("screener.page_title")}`,
    `> ${translate("screener.page_hint")}`,
    `[${translate("markdown.html_version")}](${SITE_BASE_URL}/${locale}/screener)`,
  ];

  if (!catalogue) {
    blocks.push(translate("markdown.no_indicators"));
    return `${blocks.join("\n\n")}\n`;
  }

  blocks.push(`## ${translate("markdown.definitions")}`);
  if (locale !== "en") blocks.push(translate("markdown.glossary_in_english"));
  blocks.push(indicatorTable(catalogue.indicators));

  blocks.push("## Query");
  blocks.push(queryDocumentation(catalogue));

  blocks.push(`## ${translate("screener.sector")}`);
  blocks.push(catalogue.sectors.join(", "));
  blocks.push(`## ${translate("screener.country")}`);
  blocks.push(catalogue.countries.join(", "));

  if (catalogue.unsupported_examples.length > 0) {
    blocks.push("## Not tracked");
    blocks.push(
      "Sponda does not carry these metrics. Treat any figure for them as absent, not zero: "
      + `${catalogue.unsupported_examples.join(", ")}.`,
    );
  }

  return `${blocks.join("\n\n")}\n`;
}

function indicatorTable(indicators: IndicatorCatalogueEntry[]): string {
  const lines = [
    "| Key | Name | Direction | Definition |",
    "| --- | --- | --- | --- |",
    ...indicators.map((entry) => {
      const definition = entry.note
        ? `${entry.definition} ${entry.note}`
        : entry.definition;
      const cells = [
        `\`${entry.key}\``,
        entry.name,
        directionLabel(entry.direction),
        definition,
      ];
      return `| ${cells.map(escapeTableCell).join(" | ")} |`;
    }),
  ];
  return lines.join("\n");
}

/**
 * How to reproduce the page as an API call.
 *
 * A reader who has parsed the glossary usually wants the data, not the UI,
 * and the screener endpoint is public and uncapped.
 */
function queryDocumentation(catalogue: IndicatorCatalogue): string {
  const example = catalogue.indicators[0]?.key ?? "pe10";
  return [
    "Every indicator above is a numeric filter with optional `_min` and `_max`",
    "bounds. `sort` takes any indicator key, `market_cap` or `ticker`, prefixed",
    "with `-` for descending; nulls always sort last. `limit` caps at 500.",
    "",
    "```",
    `GET ${SITE_BASE_URL}/api/screener/?${example}_max=10&debt_to_equity_max=1&sort=-market_cap&limit=50`,
    "```",
    "",
    "Returns `{ count, results[] }`. The same data is available to AI agents",
    `through Sponda's MCP server at \`${SITE_BASE_URL}/api/mcp\`.`,
  ].join("\n");
}
