/**
 * The markdown twin of a company page.
 *
 * A company page renders every number through `dynamic(..., { ssr: false })`,
 * so the HTML a crawler receives carries a title, some meta tags and no data
 * at all. This module produces the same page as plain markdown, which is what
 * `/{locale}/{TICKER}.md` serves.
 *
 * Every figure here comes from `IndicatorSnapshot` by way of
 * `/api/tickers/{symbol}/indicators/`, never from `/api/quote/{ticker}/`.
 * That endpoint syncs statements and fetches a live quote on a cache miss and
 * is capped at 20 distinct companies per IP per day; pointing 23,000
 * crawlable pages at it would exhaust the provider budget and then start
 * returning 429s. The snapshot endpoint is two indexed reads and no quota,
 * which is the only reason these pages can be generated on demand.
 *
 * Shaped after `lib/og-card.ts`, which does the same job for a different
 * output format.
 */
import { djangoApiBaseUrl } from "./django-api";
import { fetchFromDjango } from "./django-fetch";
import { markdownUrlFor } from "./markdown-routes";
import { SITE_BASE_URL } from "./site-routes";
import { translatorFor, type Translator } from "../i18n/dictionaries";
import type { SupportedLocale } from "./i18n-config";
import { currencySymbol, formatLargeNumber, formatNumber } from "../utils/format";
import { translateSector } from "../utils/sectorLabels";
import { tabSlugForLocale, type TabKey } from "../utils/tabs";

/** Ratios read the same at two decimals in every locale on the site. */
const RATIO_DECIMALS = 2;

/** Widest P/E window the snapshot carries, matching PE1..PE15 on the model. */
const MAX_PE_WINDOW = 15;

/** The analysis text is written in Portuguese and only in Portuguese. */
const ANALYSIS_LOCALE: SupportedLocale = "pt";

/** How long the snapshot endpoint's answer may be reused. Matches the
 * 15-minute cadence of the refresh_snapshot_prices timer. */
const INDICATORS_REVALIDATE_SECONDS = 900;

/** The analysis and the peer set change on the order of a quarter. */
const SLOW_REVALIDATE_SECONDS = 86400;

/** The P/E window years the snapshot carries a column for. */
type PeWindowYear = 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15;

/** `pe1` through `pe15`, each null when the company lacks the history. */
type PeWindowFields = { [Key in `pe${PeWindowYear}`]?: number | null };

/**
 * One row of `IndicatorSnapshot`, as `/api/tickers/{symbol}/indicators/`
 * serves it. Every indicator is optional and nullable: a company may have a
 * decade of earnings and no cash flow statements, or the reverse.
 */
export interface CompanySnapshot extends PeWindowFields {
  symbol: string;
  name: string;
  sector: string;
  country: string;
  reported_currency: string;
  market_cap: number | null;
  current_price: number | null;
  computed_at: string | null;
  pe_years_available?: number | null;
  pfcf10?: number | null;
  peg?: number | null;
  pfcf_peg?: number | null;
  debt_to_equity?: number | null;
  debt_ex_lease_to_equity?: number | null;
  liabilities_to_equity?: number | null;
  current_ratio?: number | null;
  debt_to_avg_earnings?: number | null;
  debt_to_avg_fcf?: number | null;
}

export interface CompanyAnalysis {
  content: string;
  generatedAt: string | null;
}

export interface CompanyPeer {
  symbol: string;
  name: string;
  sector?: string;
  market_cap?: number | null;
  pe10?: number | null;
  pfcf10?: number | null;
  peg?: number | null;
}

export interface FundamentalsYearRow {
  year: number;
  quarters?: number;
  revenue?: number | null;
  revenueAdjusted?: number | null;
  netIncome?: number | null;
  netIncomeAdjusted?: number | null;
  fcf?: number | null;
  fcfAdjusted?: number | null;
  totalDebt?: number | null;
  stockholdersEquity?: number | null;
}

export interface CompanyFundamentals {
  years: FundamentalsYearRow[];
  listingCurrency: string;
  reportedCurrency: string;
  /** Columns the HTML page shows that this view cannot fill without a
   * provider call. Named rather than silently dropped. */
  omitted: string[];
}

export interface CompanyMarkdownData {
  snapshot: CompanySnapshot | null;
  analysis: CompanyAnalysis | null;
  peers: CompanyPeer[];
  fundamentals: CompanyFundamentals | null;
}

interface MarkdownTable {
  headings: string[];
  rows: string[][];
}

type MarkdownBlock = string | MarkdownTable;

interface MarkdownSection {
  heading: string | null;
  blocks: MarkdownBlock[];
}

export interface CompanyMarkdownModel {
  title: string;
  lead: string[];
  sections: MarkdownSection[];
}

function isTable(block: MarkdownBlock): block is MarkdownTable {
  return typeof block !== "string";
}

// --- fetching -----------------------------------------------------------

async function fetchJson<T>(url: string, revalidate: number): Promise<T | null> {
  try {
    const response = await fetchFromDjango(url, { next: { revalidate } });
    if (!response || !response.ok) return null;
    return (await response.json()) as T;
  } catch {
    return null;
  }
}

/**
 * Absolute API URL for one company's snapshot.
 *
 * The extras ride on the same URL rather than on endpoints of their own so
 * that a page is one cacheable fetch. It also matters that this endpoint
 * answers 200 with a null analysis: `/api/quote/{T}/analysis/` 404s for a
 * company with no analysis, and most have none, so asking it would mean a
 * Django round trip on every view of every such page forever.
 */
export function indicatorsUrl(ticker: string, tab: TabKey): string {
  const extras: string[] = [];
  if (tab === "metrics") extras.push("analysis=1");
  if (tab === "fundamentals") extras.push("fundamentals=1");
  const query = extras.length > 0 ? `?${extras.join("&")}` : "";
  return `${djangoApiBaseUrl()}/api/tickers/${ticker}/indicators/${query}`;
}

/**
 * Everything one markdown page needs, fetched in parallel.
 *
 * Each source degrades on its own: a company with no stored analysis, or an
 * analysis endpoint having a bad minute, still yields a page with the
 * numbers on it. Only a missing snapshot means there is no page to render.
 */
export async function fetchCompanyMarkdownData(
  ticker: string,
  tab: TabKey,
): Promise<CompanyMarkdownData> {
  const upperTicker = ticker.toUpperCase();
  const apiBaseUrl = djangoApiBaseUrl();

  const [snapshot, peerList] = await Promise.all([
    fetchJson<CompanySnapshot & {
      fundamentals?: CompanyFundamentals | null;
      analysis?: { content?: string; generatedAt?: string } | null;
    }>(
      indicatorsUrl(upperTicker, tab),
      INDICATORS_REVALIDATE_SECONDS,
    ),
    tab === "compare"
      ? fetchJson<CompanyPeer[]>(
          `${apiBaseUrl}/api/tickers/${upperTicker}/peers/`,
          SLOW_REVALIDATE_SECONDS,
        )
      : Promise.resolve(null),
  ]);

  const analysisPayload = snapshot?.analysis;
  return {
    snapshot: snapshot && snapshot.symbol ? snapshot : null,
    analysis: analysisPayload?.content
      ? { content: analysisPayload.content, generatedAt: analysisPayload.generatedAt ?? null }
      : null,
    peers: await hydratePeers(peerList, apiBaseUrl),
    fundamentals: snapshot?.fundamentals ?? null,
  };
}

/** Fill the peer rows with their own indicators, in one extra request. */
async function hydratePeers(
  peers: CompanyPeer[] | null,
  apiBaseUrl: string,
): Promise<CompanyPeer[]> {
  if (!peers || peers.length === 0) return [];

  const symbols = peers.map((peer) => peer.symbol).join(",");
  const bulk = await fetchJson<{ companies: Record<string, CompanySnapshot> }>(
    `${apiBaseUrl}/api/tickers/${peers[0].symbol}/indicators/?symbols=${symbols}`,
    INDICATORS_REVALIDATE_SECONDS,
  );
  const companies = bulk?.companies ?? {};

  return peers.map((peer) => {
    const snapshot = companies[peer.symbol.toUpperCase()];
    if (!snapshot) return peer;
    return {
      ...peer,
      market_cap: numberOrNull(snapshot.market_cap),
      pe10: numberOrNull(snapshot.pe10),
      pfcf10: numberOrNull(snapshot.pfcf10),
      peg: numberOrNull(snapshot.peg),
    };
  });
}

// --- formatting ---------------------------------------------------------

function numberOrNull(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

/**
 * Put the minus sign back.
 *
 * `formatNumber` swaps the ASCII hyphen for an en dash, which is right for a
 * page a person reads and wrong for a document a machine parses: a model that
 * does not recognise U+2013 as a minus reads a loss as a profit. The digits
 * are identical either way, so this changes nothing but the glyph.
 */
function asciiMinus(formatted: string): string {
  return formatted.replace(/[\u2012\u2013\u2014\u2212]/g, "-");
}

/**
 * One P/E window off the snapshot.
 *
 * The cast is the price of iterating `pe1`..`pe15` in a loop rather than
 * writing fifteen field accesses; `PeWindowYear` keeps the loop honest about
 * which columns exist.
 */
function peWindow(snapshot: CompanySnapshot, years: PeWindowYear): number | null {
  return numberOrNull((snapshot as unknown as Record<string, unknown>)[`pe${years}`]);
}

function ratio(value: unknown, locale: SupportedLocale): string | null {
  const parsed = numberOrNull(value);
  return parsed === null ? null : asciiMinus(formatNumber(parsed, RATIO_DECIMALS, locale));
}

/**
 * A share price, at full precision.
 *
 * Not `formatLargeNumber`: that abbreviates and drops the decimals below a
 * thousand, which would render a 35.75 price as "R$ 36".
 */
function price(
  value: unknown,
  locale: SupportedLocale,
  ticker: string,
  reportedCurrency?: string,
): string | null {
  const parsed = numberOrNull(value);
  if (parsed === null) return null;
  const symbol = currencySymbol(ticker, reportedCurrency);
  return `${symbol} ${asciiMinus(formatNumber(parsed, RATIO_DECIMALS, locale))}`;
}

/** `YYYY-MM-DD` from an ISO timestamp, or null if there isn't one. */
function isoDate(timestamp: string | null | undefined): string | null {
  return timestamp ? timestamp.slice(0, 10) : null;
}

/** A table row, or null when the value is missing so the caller can drop it. */
function indicatorRow(label: string, value: string | null): string[] | null {
  return value === null ? null : [label, value];
}

function compactRows(rows: (string[] | null)[]): string[][] {
  return rows.filter((row): row is string[] => row !== null);
}

/**
 * Push every heading in the stored analysis two levels down.
 *
 * The analysis is authored as a standalone document and opens at `#`. Pasted
 * under the page's own `#` title it would produce two top-level headings and
 * a broken outline for anything parsing the structure.
 */
function demoteHeadings(markdown: string): string {
  return markdown.replace(/^(#{1,4})(\s)/gm, "##$1$2");
}

// --- model --------------------------------------------------------------

interface CompanyMarkdownModelInput {
  ticker: string;
  locale: SupportedLocale;
  tab: TabKey;
  data: CompanyMarkdownData;
}

function absoluteUrl(path: string): string {
  return `${SITE_BASE_URL}${path}`;
}

function htmlPageUrl(locale: string, ticker: string, tab: TabKey): string {
  const slug = tabSlugForLocale(locale, tab);
  return absoluteUrl(slug ? `/${locale}/${ticker}/${slug}` : `/${locale}/${ticker}`);
}

function buildLead(
  ticker: string,
  locale: SupportedLocale,
  tab: TabKey,
  translate: Translator,
  snapshot: CompanySnapshot | null,
): string[] {
  const descriptors: string[] = [];
  if (snapshot?.sector) descriptors.push(translateSector(snapshot.sector, locale));
  if (snapshot?.country) descriptors.push(snapshot.country);
  if (snapshot?.reported_currency) {
    descriptors.push(translate("markdown.reports_in", { currency: snapshot.reported_currency }));
  }

  const lead: string[] = [];
  if (descriptors.length > 0) lead.push(`> ${descriptors.join(" · ")}`);
  lead.push(translate("markdown.intro"));
  lead.push(`[${translate("markdown.html_version")}](${htmlPageUrl(locale, ticker, tab)})`);
  return lead;
}

function valuationSection(
  snapshot: CompanySnapshot,
  locale: SupportedLocale,
  translate: Translator,
): MarkdownSection {
  const rows = compactRows([
    indicatorRow("P/E10", ratio(snapshot.pe10, locale)),
    indicatorRow("P/FCF10", ratio(snapshot.pfcf10, locale)),
    indicatorRow("PEG", ratio(snapshot.peg, locale)),
    indicatorRow("PFCF-PEG", ratio(snapshot.pfcf_peg, locale)),
  ]);

  const blocks: MarkdownBlock[] = [];
  if (rows.length > 0) {
    blocks.push({
      headings: [translate("markdown.col_indicator"), translate("markdown.col_value")],
      rows,
    });
  }
  const windowYears = numberOrNull(snapshot.pe_years_available);
  if (windowYears !== null) {
    blocks.push(translate("markdown.widest_window", { years: windowYears }));
  }
  return { heading: translate("markdown.section_valuation"), blocks };
}

function priceSection(
  snapshot: CompanySnapshot,
  locale: SupportedLocale,
  translate: Translator,
): MarkdownSection | null {
  const currency = snapshot.reported_currency || undefined;
  const marketCap = numberOrNull(snapshot.market_cap);

  const rows = compactRows([
    indicatorRow(
      translate("metrics.current_price"),
      price(snapshot.current_price, locale, snapshot.symbol, currency),
    ),
    indicatorRow(
      translate("metrics.market_cap"),
      marketCap === null
        ? null
        : asciiMinus(formatLargeNumber(marketCap, snapshot.symbol, locale, currency)),
    ),
  ]);
  if (rows.length === 0) return null;

  return {
    heading: translate("markdown.section_price"),
    blocks: [{
      headings: [translate("markdown.col_indicator"), translate("markdown.col_value")],
      rows,
    }],
  };
}

function leverageSection(
  snapshot: CompanySnapshot,
  locale: SupportedLocale,
  translate: Translator,
): MarkdownSection | null {
  const rows = compactRows([
    indicatorRow(translate("metrics.gross_debt_equity"), ratio(snapshot.debt_to_equity, locale)),
    indicatorRow(translate("metrics.debt_ex_lease_equity"), ratio(snapshot.debt_ex_lease_to_equity, locale)),
    indicatorRow(translate("metrics.liab_equity"), ratio(snapshot.liabilities_to_equity, locale)),
    indicatorRow(translate("metrics.current_ratio"), ratio(snapshot.current_ratio, locale)),
  ]);
  if (rows.length === 0) return null;

  return {
    heading: translate("markdown.section_leverage"),
    blocks: [{
      headings: [translate("markdown.col_indicator"), translate("markdown.col_value")],
      rows,
    }],
  };
}

function debtCoverageSection(
  snapshot: CompanySnapshot,
  locale: SupportedLocale,
  translate: Translator,
): MarkdownSection | null {
  const rows = compactRows([
    indicatorRow(translate("metrics.gross_debt_earnings"), ratio(snapshot.debt_to_avg_earnings, locale)),
    indicatorRow(translate("metrics.gross_debt_fcf"), ratio(snapshot.debt_to_avg_fcf, locale)),
  ]);
  if (rows.length === 0) return null;

  return {
    heading: translate("markdown.section_debt_coverage"),
    blocks: [{
      headings: [translate("markdown.col_indicator"), translate("markdown.col_value")],
      rows,
    }],
  };
}

/**
 * PE1..PE15 as a table.
 *
 * This is the shape the charts tab draws: how the multiple moves as the
 * earnings window lengthens. Windows the company lacks the history for are
 * labelled as such rather than left blank, because a blank cell reads as
 * "zero" to something parsing the table.
 */
function peWindowSection(
  snapshot: CompanySnapshot,
  locale: SupportedLocale,
  translate: Translator,
): MarkdownSection {
  const unavailable = translate("markdown.unavailable_window");
  const rows: string[][] = [];
  for (let years = 1; years <= MAX_PE_WINDOW; years += 1) {
    const window = years as PeWindowYear;
    rows.push([`P/E${years}`, ratio(peWindow(snapshot, window), locale) ?? unavailable]);
  }

  const blocks: MarkdownBlock[] = [{
    headings: [translate("markdown.col_window"), translate("markdown.col_value")],
    rows,
  }];
  const windowYears = numberOrNull(snapshot.pe_years_available);
  if (windowYears !== null) {
    blocks.push(translate("markdown.widest_window", { years: windowYears }));
  }
  return { heading: translate("markdown.section_pe_windows"), blocks };
}

function peersSection(
  peers: CompanyPeer[],
  locale: SupportedLocale,
  translate: Translator,
): MarkdownSection {
  if (peers.length === 0) {
    return {
      heading: translate("markdown.section_peers"),
      blocks: [translate("markdown.no_peers")],
    };
  }

  const missing = translate("common.na");
  return {
    heading: translate("markdown.section_peers"),
    blocks: [{
      headings: [
        translate("screener.col_ticker"),
        translate("markdown.col_company"),
        "P/E10",
        "P/FCF10",
        "PEG",
      ],
      rows: peers.map((peer) => [
        peer.symbol,
        peer.name,
        ratio(peer.pe10, locale) ?? missing,
        ratio(peer.pfcf10, locale) ?? missing,
        ratio(peer.peg, locale) ?? missing,
      ]),
    }],
  };
}

function annualSection(
  fundamentals: CompanyFundamentals,
  snapshot: CompanySnapshot,
  locale: SupportedLocale,
  translate: Translator,
): MarkdownSection {
  const currency = fundamentals.reportedCurrency || snapshot.reported_currency;
  const missing = translate("common.na");
  const money = (value: number | null | undefined): string => {
    const parsed = numberOrNull(value);
    return parsed === null
      ? missing
      : asciiMinus(formatLargeNumber(parsed, snapshot.symbol, locale, currency));
  };

  const blocks: MarkdownBlock[] = [];
  if (fundamentals.years.length > 0) {
    blocks.push({
      headings: [
        translate("markdown.col_year"),
        translate("fundamentals.col.revenue"),
        translate("fundamentals.col.net_income"),
        translate("fundamentals.col.fcf"),
        translate("fundamentals.col.debt"),
        translate("fundamentals.col.equity"),
      ],
      rows: fundamentals.years.map((row) => [
        String(row.year),
        money(row.revenueAdjusted ?? row.revenue),
        money(row.netIncomeAdjusted ?? row.netIncome),
        money(row.fcfAdjusted ?? row.fcf),
        money(row.totalDebt),
        money(row.stockholdersEquity),
      ]),
    });
  }
  if (fundamentals.omitted.length > 0) {
    blocks.push(translate("markdown.omitted_columns", { columns: fundamentals.omitted.join(", ") }));
  }
  return { heading: translate("markdown.section_annual"), blocks };
}

function analysisSection(
  analysis: CompanyAnalysis,
  locale: SupportedLocale,
  translate: Translator,
): MarkdownSection {
  const blocks: MarkdownBlock[] = [];
  if (locale !== ANALYSIS_LOCALE) {
    blocks.push(translate("markdown.analysis_in_portuguese"));
  }
  blocks.push(demoteHeadings(analysis.content.trim()));
  return { heading: translate("markdown.section_analysis"), blocks };
}

/** Links to the same company's other pages, markdown first. */
function otherViewsSection(
  ticker: string,
  locale: SupportedLocale,
  tab: TabKey,
  translate: Translator,
): MarkdownSection {
  const otherTabs: TabKey[] = (["metrics", "charts", "fundamentals", "compare"] as TabKey[])
    .filter((candidate) => candidate !== tab);

  const links = otherTabs.map((candidate) => {
    const label = candidate === "metrics"
      ? translate("tabs.metrics")
      : translate(`tabs.${candidate}` as "tabs.charts");
    return `- [${label}](${absoluteUrl(markdownUrlFor(locale, ticker, candidate))})`;
  });
  links.push(
    `- [${translate("markdown.definitions")}](${absoluteUrl(`/${locale}/screener.md`)})`,
  );

  return { heading: translate("markdown.section_other_views"), blocks: [links.join("\n")] };
}

/** Everything the page prints, resolved and formatted ahead of rendering. */
export function buildCompanyMarkdownModel({
  ticker,
  locale,
  tab,
  data,
}: CompanyMarkdownModelInput): CompanyMarkdownModel {
  const translate = translatorFor(locale);
  const upperTicker = ticker.toUpperCase();
  const { snapshot } = data;
  const title = snapshot?.name ? `${snapshot.name} (${upperTicker})` : upperTicker;
  const lead = buildLead(upperTicker, locale, tab, translate, snapshot);

  if (!snapshot) {
    return {
      title,
      lead,
      sections: [
        { heading: null, blocks: [translate("markdown.no_indicators")] },
        otherViewsSection(upperTicker, locale, tab, translate),
      ],
    };
  }

  const sections: MarkdownSection[] = [];

  if (tab === "charts") {
    sections.push(peWindowSection(snapshot, locale, translate));
  } else if (tab === "compare") {
    sections.push(valuationSection(snapshot, locale, translate));
    sections.push(peersSection(data.peers, locale, translate));
  } else if (tab === "fundamentals") {
    if (data.fundamentals) {
      sections.push(annualSection(data.fundamentals, snapshot, locale, translate));
    }
    const leverage = leverageSection(snapshot, locale, translate);
    if (leverage) sections.push(leverage);
    const coverage = debtCoverageSection(snapshot, locale, translate);
    if (coverage) sections.push(coverage);
  } else {
    const price = priceSection(snapshot, locale, translate);
    if (price) sections.push(price);
    sections.push(valuationSection(snapshot, locale, translate));
    const leverage = leverageSection(snapshot, locale, translate);
    if (leverage) sections.push(leverage);
    const coverage = debtCoverageSection(snapshot, locale, translate);
    if (coverage) sections.push(coverage);
    if (data.analysis) sections.push(analysisSection(data.analysis, locale, translate));
  }

  sections.push(otherViewsSection(upperTicker, locale, tab, translate));

  const asOf = isoDate(snapshot.computed_at);
  if (asOf) {
    sections.push({ heading: null, blocks: [translate("markdown.data_as_of", { date: asOf })] });
  }

  return { title, lead, sections };
}

// --- rendering ----------------------------------------------------------

/**
 * Make one value safe to put between two pipes.
 *
 * A company name or a sector label with a `|` in it would otherwise split
 * into two columns and corrupt every row below it.
 */
export function escapeTableCell(value: string): string {
  return value.replace(/\|/g, "\\|").replace(/\r?\n/g, " ");
}

function renderRow(cells: string[]): string {
  return `| ${cells.map(escapeTableCell).join(" | ")} |`;
}

function renderTable(table: MarkdownTable): string {
  const lines = [
    renderRow(table.headings),
    `| ${table.headings.map(() => "---").join(" | ")} |`,
    ...table.rows.map(renderRow),
  ];
  return lines.join("\n");
}

function renderSection(section: MarkdownSection): string {
  const parts = section.heading ? [`## ${section.heading}`] : [];
  for (const block of section.blocks) {
    parts.push(isTable(block) ? renderTable(block) : block);
  }
  return parts.join("\n\n");
}

/** The finished document. Pure and synchronous: give it a model, get text. */
export function renderCompanyMarkdown(model: CompanyMarkdownModel): string {
  const blocks = [`# ${model.title}`, ...model.lead, ...model.sections.map(renderSection)];
  return `${blocks.filter(Boolean).join("\n\n")}\n`;
}
