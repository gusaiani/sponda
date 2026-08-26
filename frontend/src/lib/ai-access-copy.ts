/**
 * The content of the "For AI agents" page.
 *
 * Held as data rather than JSX so the HTML page at `/{locale}/for-ai` and its
 * markdown twin at `/{locale}/for-ai.md` render from one source. A page whose
 * whole subject is machine-readable access would be a poor advertisement for
 * itself if the two versions disagreed.
 *
 * English only, deliberately. The audience is whoever is wiring Sponda into a
 * program, and the identifiers, endpoints and field names on this page are
 * English regardless of the reader's locale. Translating the prose around
 * them would create seven copies to keep in step for no gain.
 */
import { SITE_BASE_URL } from "./site-routes";

export interface AiAccessSection {
  heading: string;
  /** Paragraphs and fenced blocks, in order. A block starts with "```". */
  body: string[];
}

export const AI_ACCESS_TITLE = "Reading Sponda from a program";

export const AI_ACCESS_INTRO =
  "Sponda holds inflation-adjusted valuation and quality indicators for "
  + "listed companies in the U.S. and Brazil. Every figure on the site is "
  + "available to software four ways, listed here cheapest first.";

export const AI_ACCESS_SECTIONS: AiAccessSection[] = [
  {
    heading: "MCP server",
    body: [
      "The best option if you are building on an assistant. Sponda is an MCP "
      + "server, so the model can screen and look up companies as tool calls "
      + "rather than by fetching and parsing pages.",
      "```\n" + `${SITE_BASE_URL}/api/mcp` + "\n```",
      "Streamable HTTP, stateless, no authentication. In Claude Code:",
      "```\nclaude mcp add --transport http sponda " + `${SITE_BASE_URL}/api/mcp/` + "\n```",
      "Tools: `list_available_indicators`, `screen_companies`, `get_company`, "
      + "`get_fundamentals`. Call `list_available_indicators` first; it returns "
      + "the exact indicator keys, the countries and sectors present in the "
      + "data, and an explicit list of metrics Sponda does not track.",
    ],
  },
  {
    heading: "Markdown pages",
    body: [
      "Every public page is also served as plain markdown at the same URL with "
      + "`.md` appended. The HTML renders its numbers client-side and carries "
      + "none of them; the markdown carries the table.",
      "```\n"
      + `${SITE_BASE_URL}/en/PETR4.md\n`
      + `${SITE_BASE_URL}/en/PETR4/charts.md\n`
      + `${SITE_BASE_URL}/en/PETR4/fundamentals.md\n`
      + `${SITE_BASE_URL}/en/PETR4/compare.md\n`
      + `${SITE_BASE_URL}/en/screener.md\n`
      + "```",
      "The tab slug is localized: `charts` is `graficos` in Portuguese and "
      + "Spanish, `graphiques` in French, `diagramme` in German, `grafici` in "
      + "Italian. A company page with no locale prefix, such as `/PETR4.md`, is "
      + "served in English rather than redirected, so a guessed URL still works.",
      "Every HTML page advertises its twin twice: a "
      + "`<link rel=\"alternate\" type=\"text/markdown\">` tag in the document, "
      + "and a `Link:` response header carrying the same URL. A `HEAD` request "
      + "is enough to discover it.",
    ],
  },
  {
    heading: "JSON endpoints",
    body: [
      "Public, uncapped, and the same data the markdown pages are rendered from.",
      "```\n"
      + `GET ${SITE_BASE_URL}/api/screener/?pe10_max=10&debt_to_equity_max=1&sort=-market_cap&limit=50\n`
      + `GET ${SITE_BASE_URL}/api/tickers/{SYMBOL}/indicators/\n`
      + `GET ${SITE_BASE_URL}/api/tickers/{SYMBOL}/indicators/?symbols=A,B,C\n`
      + `GET ${SITE_BASE_URL}/api/tickers/symbols/\n`
      + `GET ${SITE_BASE_URL}/api/assistant/indicators/\n`
      + "```",
      "`/api/tickers/symbols/` returns every listed company symbol and nothing "
      + "else, about 150KB, which is the cheapest way to learn the universe. "
      + "`/api/assistant/indicators/` returns the indicator glossary with "
      + "definitions and which direction is better.",
      "One endpoint is capped. `/api/quote/{TICKER}/` is richer than "
      + "`/indicators/` but fetches from upstream data providers, so it is "
      + "limited to 20 distinct companies per day per IP and answers `429` past "
      + "that. Use the markdown pages or the endpoints above to read at volume.",
    ],
  },
  {
    heading: "Finding everything",
    body: [
      "```\n"
      + `${SITE_BASE_URL}/llms.txt\n`
      + `${SITE_BASE_URL}/sitemap.xml\n`
      + "```",
      "`llms.txt` describes the conventions on this page in a form meant to be "
      + "read rather than rendered. `sitemap.xml` is an index; its children "
      + "under `/sitemaps/` enumerate every company page, so nothing has to be "
      + "guessed.",
      "Blog posts are markdown too, at their permalink plus `index.md`.",
    ],
  },
  {
    heading: "What Sponda does not have",
    body: [
      "Treat any figure for these as absent rather than zero: return on equity, "
      + "dividend yield, revenue growth, analyst price targets, news, and "
      + "recent events. `list_available_indicators` returns the authoritative "
      + "list.",
      "One convention is load-bearing. A P/E window is empty unless the company "
      + "has the full history for it, so a P/E15 is never quietly a P/E8. "
      + "`pe_years_available` tells you the widest window a company can fill. An "
      + "absent indicator means absent data, never zero.",
    ],
  },
];
