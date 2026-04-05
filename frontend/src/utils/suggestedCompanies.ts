import type { Region } from "./region";

/* ── Default homepage cards (8 tickers) ── */

const BRAZIL_DEFAULT_TICKERS = [
  "PETR4", "VALE3", "ITUB4", "WEGE3",
  "ABEV3", "BBAS3", "RENT3", "SUZB3",
];

const US_DEFAULT_TICKERS = [
  "AAPL", "MSFT", "GOOGL", "AMZN",
  "NVDA", "META", "TSLA", "JPM",
];

const EUROPE_DEFAULT_TICKERS = [
  "ASML", "NVO", "SAP", "AZN",
  "SHEL", "UL", "TM", "HSBC",
];

const ASIA_DEFAULT_TICKERS = [
  "TSM", "SONY", "TM", "BABA",
  "HMC", "MUFG", "INFY", "LI",
];

/* ── Popular companies grid (40 + extra pool) ── */

const BRAZIL_POPULAR_SYMBOLS = [
  "PETR4", "VALE3", "ITUB4", "BBDC4", "BBAS3",
  "WEGE3", "ABEV3", "B3SA3", "RENT3", "SUZB3",
  "ITSA4", "ELET3", "JBSS3", "RADL3", "EQTL3",
  "VIVT3", "PRIO3", "LREN3", "TOTS3", "SBSP3",
  "GGBR4", "CSNA3", "CSAN3", "KLBN11", "ENEV3",
  "HAPV3", "RDOR3", "RAIL3", "BBSE3", "CPLE6",
  "UGPA3", "CMIG4", "TAEE11", "EMBR3", "FLRY3",
  "ARZZ3", "MULT3", "PETZ3", "VBBR3", "MGLU3",
  "COGN3", "CYRE3", "EGIE3", "GOAU4", "HYPE3",
  "IRBR3", "MRFG3", "NTCO3", "QUAL3", "SANB11",
  "SLCE3", "SMTO3", "SULA11", "TIMS3", "USIM5",
  "YDUQ3", "AZUL4", "BRFS3", "CCRO3", "CIEL3",
];

const US_POPULAR_SYMBOLS = [
  "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
  "META", "TSLA", "JPM", "BRK.B", "UNH",
  "V", "MA", "JNJ", "PG", "HD",
  "XOM", "COST", "ABBV", "KO", "PEP",
  "MRK", "LLY", "AVGO", "CRM", "NFLX",
  "ORCL", "ACN", "ADBE", "CSCO", "AMD",
  "WMT", "DIS", "NKE", "BA", "GS",
  "CAT", "UPS", "MCD", "SBUX", "INTC",
  "T", "VZ", "IBM", "GE", "CVX",
  "COP", "NEE", "LOW", "ISRG", "GILD",
  "AMGN", "MDLZ", "TGT", "F", "GM",
  "SO", "DUK", "PYPL", "TMO", "SLB",
];

const EUROPE_POPULAR_SYMBOLS = [
  // European ADRs on US exchanges
  "ASML", "NVO", "SAP", "AZN", "SHEL",
  "UL", "HSBC", "TTE", "SNY", "DEO",
  "GSK", "BCS", "PHG", "ERIC", "NOK",
  "SAN", "BBVA", "ING", "DB", "UBS",
  "ABB", "SPOT", "SE", "SHOP", "LULU",
  // Major US companies as global fills
  "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
  "META", "TSLA", "JPM", "V", "MA",
  "JNJ", "PG", "KO", "NFLX", "DIS",
  "MRK", "LLY", "AVGO", "CRM", "AMD",
  "ORCL", "ADBE", "WMT", "NKE", "BA",
  "MCD", "SBUX", "COST", "HD", "PEP",
  "GS", "CAT", "IBM", "GE", "XOM",
];

const ASIA_POPULAR_SYMBOLS = [
  // Asian ADRs on US exchanges
  "TSM", "SONY", "TM", "BABA", "HMC",
  "MUFG", "INFY", "LI", "NIO", "BIDU",
  "JD", "PDD", "WIT", "KB", "SHG",
  "MFG", "SMFG", "IBN", "XPEV", "SE",
  // Major US companies as global fills
  "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
  "META", "TSLA", "JPM", "V", "MA",
  "JNJ", "PG", "KO", "NFLX", "DIS",
  "MRK", "LLY", "AVGO", "CRM", "AMD",
  "ORCL", "ADBE", "WMT", "NKE", "BA",
  "MCD", "SBUX", "COST", "HD", "PEP",
  "GS", "CAT", "IBM", "GE", "XOM",
];

const DEFAULT_TICKERS: Record<Region, string[]> = {
  brazil: BRAZIL_DEFAULT_TICKERS,
  us: US_DEFAULT_TICKERS,
  europe: EUROPE_DEFAULT_TICKERS,
  asia: ASIA_DEFAULT_TICKERS,
};

const POPULAR_SYMBOLS: Record<Region, string[]> = {
  brazil: BRAZIL_POPULAR_SYMBOLS,
  us: US_POPULAR_SYMBOLS,
  europe: EUROPE_POPULAR_SYMBOLS,
  asia: ASIA_POPULAR_SYMBOLS,
};

export function getDefaultTickers(region: Region): string[] {
  return DEFAULT_TICKERS[region];
}

export function getPopularSymbols(region: Region): string[] {
  return POPULAR_SYMBOLS[region];
}
