/**
 * `/llms.txt` · what Sponda is and how to read it, for a machine.
 *
 * Generated rather than static. The file this replaced was hand-written and
 * had drifted: it advertised `/{TICKER}/fundamentos`, a URL the middleware
 * 302s away from because every page is locale-prefixed now. Anything stated
 * here that can be derived is derived, so it cannot go stale again.
 *
 * `frontend/public/llms.txt` had to be deleted for this route to be reached:
 * Next serves the public directory ahead of app routes.
 */
import { fetchIndicatorCatalogue, type IndicatorCatalogue } from "../../lib/site-markdown";
import { INDEXABLE_LOCALES, SUPPORTED_LOCALES } from "../../lib/i18n-config";
import { SITE_BASE_URL } from "../../lib/site-routes";

export const runtime = "nodejs";

const ONE_DAY_IN_SECONDS = 86400;
const ONE_WEEK_IN_SECONDS = 604800;

/** Canonical tab slugs, in English. Every locale has its own; the file says so. */
const TAB_SLUGS = ["charts", "fundamentals", "compare"];

function header(): string[] {
  return [
    "# Sponda",
    "",
    "> Fundamental analysis indicators for global stocks, adjusted for inflation.",
    "",
    "Sponda is a free platform for value investors analyzing publicly traded",
    "companies worldwide. It calculates valuation and quality metrics from",
    "inflation-adjusted historical data, covering roughly 23,000 listed",
    "companies across the U.S. and Brazil.",
  ];
}

/**
 * The section that earns the file its keep.
 *
 * Every page is also served as markdown at the same URL plus `.md`. Saying
 * so once, here, saves a model from parsing HTML that carries no data.
 */
function markdownSection(): string[] {
  return [
    "## Markdown",
    "",
    "Every public page is also served as plain markdown at the same URL with",
    "`.md` appended. The markdown carries the numbers; the HTML renders them",
    "client-side and does not.",
    "",
    `- \`${SITE_BASE_URL}/{locale}/{TICKER}.md\` · indicators for one company`,
    ...TAB_SLUGS.map(
      (slug) => `- \`${SITE_BASE_URL}/{locale}/{TICKER}/${slug}.md\` · the ${slug} view`,
    ),
    `- \`${SITE_BASE_URL}/{locale}/screener.md\` · indicator definitions and the query API`,
    `- \`${SITE_BASE_URL}/{locale}.md\` · what Sponda measures`,
    "",
    "The tab slug is localized: `charts` is `graficos` in pt and es,",
    "`graphiques` in fr, `diagramme` in de, `grafici` in it. A company page",
    "with no locale prefix, such as `/PETR4.md`, is served in English rather",
    "than redirected.",
  ];
}

function localeSection(): string[] {
  return [
    "## Locales",
    "",
    `Supported: ${SUPPORTED_LOCALES.join(", ")}.`,
    `Indexed: ${INDEXABLE_LOCALES.join(", ")}.`,
    "A URL without a locale prefix redirects to one based on Accept-Language,",
    "so prefer the prefixed form when fetching.",
  ];
}

function indicatorSection(catalogue: IndicatorCatalogue | null): string[] {
  if (!catalogue) {
    return [
      "## Indicators",
      "",
      `The full catalogue, with definitions, is at ${SITE_BASE_URL}/en/screener.md.`,
    ];
  }

  // The fifteen strict P/E windows share one definition; listing them
  // individually would be most of the file and none of the information.
  const peWindows = catalogue.indicators.filter(({ key }) => /^pe\d+$/.test(key));
  const rest = catalogue.indicators.filter(({ key }) => !/^pe\d+$/.test(key));

  return [
    "## Indicators",
    "",
    ...(peWindows.length > 0
      ? [
          `- \`pe1\` .. \`pe${peWindows.length}\` · market cap over inflation-adjusted average`,
          "  net income across exactly that many years. A window is empty unless the",
          "  company has the full history for it, so a P/E15 is never quietly a P/E8.",
          "  `pe10` is the Shiller P/E.",
        ]
      : []),
    ...rest.map((entry) => `- \`${entry.key}\` (${entry.name}) · ${entry.definition}`),
    "",
    `Sectors: ${catalogue.sectors.join(", ")}.`,
    `Countries: ${catalogue.countries.join(", ")}.`,
    "",
    "Not tracked. Treat any figure for these as absent, not zero: "
      + `${catalogue.unsupported_examples.join(", ")}.`,
  ];
}

function apiSection(): string[] {
  return [
    "## Data access",
    "",
    `- \`GET ${SITE_BASE_URL}/api/screener/?pe10_max=10&sort=-market_cap&limit=50\``,
    "  filter and rank the whole universe. Returns `{ count, results[] }`.",
    `- \`GET ${SITE_BASE_URL}/api/tickers/{SYMBOL}/indicators/\``,
    "  every indicator for one company, as JSON. This is what the markdown",
    "  pages are rendered from.",
    `- \`${SITE_BASE_URL}/api/mcp\` · MCP server, for AI assistants.`,
    `- \`${SITE_BASE_URL}/sitemap.xml\``,
    "",
    "`/api/quote/{TICKER}/` also exists and is richer, but it is rate limited",
    "to 20 distinct companies per day per IP because it fetches from upstream",
    "data providers. Use the markdown pages or the screener endpoint to read",
    "at any volume.",
  ];
}

function footer(): string[] {
  return [
    "## About",
    "",
    "Sponda is maintained by Poema Parceria de Investimentos (https://poe.ma).",
    `Blog: https://blog.sponda.capital/`,
  ];
}

export async function GET(): Promise<Response> {
  const catalogue = await fetchIndicatorCatalogue();

  const body = [
    header(),
    markdownSection(),
    localeSection(),
    indicatorSection(catalogue),
    apiSection(),
    footer(),
  ]
    .map((section) => section.join("\n"))
    .join("\n\n");

  return new Response(`${body}\n`, {
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "Cache-Control": `public, max-age=${ONE_DAY_IN_SECONDS}, stale-while-revalidate=${ONE_WEEK_IN_SECONDS}`,
    },
  });
}
