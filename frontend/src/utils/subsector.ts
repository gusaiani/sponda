/**
 * Infer a sub-sector from a company's name and BRAPI sector.
 *
 * BRAPI's sector field is very broad (e.g. "Finance" includes banks,
 * insurers, real estate, logistics). This function uses name-based
 * heuristics to produce a more specific grouping so that peers in the
 * comparison table are actually comparable.
 */

interface SubsectorRule {
  /** Substring or regex to match against the company name (case-insensitive) */
  pattern: RegExp;
  subsector: string;
}

const FINANCE_RULES: SubsectorRule[] = [
  { pattern: /\bBCO\b|BANCO\b|BANESTES|ITAU|BRADESC|BANESE/i, subsector: "Bancos" },
  { pattern: /SEGUR|SEGURAD|RESSEGURO/i, subsector: "Seguros" },
  { pattern: /CONSTRU|INCORPOR|EMPREEND.*IMOB|REALTY|ENGENHARIA|TENDA|CURY|CYRELA|DIRECIONAL|EVEN|GAFISA|LAVVI|MITRE|MOURA|PLANO|TECNISA|PDG|ALPHAVILLE/i, subsector: "Construção e Incorporação" },
  { pattern: /SHOPPING|IGUATEMI|MULTIPLAN|ALLOS/i, subsector: "Shoppings" },
  { pattern: /LOCAÇÃO|LOCACAO|RENT A CAR|MOVIDA|VAMOS|ARMAC|MILLS/i, subsector: "Locação" },
  { pattern: /AGRO|AGRICOLA|TERRA SANTA/i, subsector: "Agronegócio" },
  { pattern: /BOLSA|BALCÃO|B3 S\.A/i, subsector: "Infraestrutura de Mercado" },
  { pattern: /HOLDING|PARTICIPAC/i, subsector: "Holdings" },
];

export function getSubsector(name: string, sector: string): string {
  if (sector === "Finance") {
    for (const rule of FINANCE_RULES) {
      if (rule.pattern.test(name)) return rule.subsector;
    }
  }
  return sector;
}

/**
 * Find same-subsector peers for a given company.
 *
 * Falls back to the broader sector if the subsector yields fewer than
 * `minPeers` results, ensuring the comparison table is never too sparse.
 */
export function getSectorPeers(
  currentSymbol: string,
  currentName: string,
  currentSector: string,
  allTickers: { symbol: string; name: string; sector: string }[],
  maxPeers = 10,
  minPeers = 3,
): string[] {
  const subsector = getSubsector(currentName, currentSector);

  // Try subsector match first
  const subsectorPeers = allTickers
    .filter(
      (t) =>
        t.symbol !== currentSymbol &&
        t.sector === currentSector &&
        getSubsector(t.name, t.sector) === subsector,
    )
    .slice(0, maxPeers)
    .map((t) => t.symbol);

  if (subsectorPeers.length >= minPeers) return subsectorPeers;

  // Fall back to broader sector
  return allTickers
    .filter((t) => t.symbol !== currentSymbol && t.sector === currentSector)
    .slice(0, maxPeers)
    .map((t) => t.symbol);
}
