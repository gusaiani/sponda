/** Localized country names keyed by ISO 3166-1 alpha-2 code.
 *
 * Lives outside the main i18n dictionary so onboarding a new country
 * (e.g. when an ADR from a less-common jurisdiction enters the screener)
 * is a one-line edit here rather than touching every locale file.
 *
 * Entries cover the G20 + major developed markets + the most common ADR
 * origin countries. Unknown codes fall back to the raw ISO string,
 * which keeps the UI functional while signalling that the dictionary
 * needs updating.
 */
const EN_COUNTRY_LABELS: Record<string, string> = {
  AR: "Argentina",
  AT: "Austria",
  AU: "Australia",
  BE: "Belgium",
  BR: "Brazil",
  CA: "Canada",
  CH: "Switzerland",
  CL: "Chile",
  CN: "China",
  CO: "Colombia",
  CZ: "Czech Republic",
  DE: "Germany",
  DK: "Denmark",
  ES: "Spain",
  FI: "Finland",
  FR: "France",
  GB: "United Kingdom",
  GR: "Greece",
  HK: "Hong Kong",
  HU: "Hungary",
  ID: "Indonesia",
  IE: "Ireland",
  IL: "Israel",
  IN: "India",
  IS: "Iceland",
  IT: "Italy",
  JP: "Japan",
  KR: "South Korea",
  KY: "Cayman Islands",
  LU: "Luxembourg",
  MX: "Mexico",
  MY: "Malaysia",
  NL: "Netherlands",
  NO: "Norway",
  NZ: "New Zealand",
  PE: "Peru",
  PH: "Philippines",
  PL: "Poland",
  PT: "Portugal",
  RU: "Russia",
  SA: "Saudi Arabia",
  SE: "Sweden",
  SG: "Singapore",
  TH: "Thailand",
  TR: "Turkey",
  TW: "Taiwan",
  US: "United States",
  ZA: "South Africa",
};

const PT_COUNTRY_LABELS: Record<string, string> = {
  AR: "Argentina",
  AT: "Áustria",
  AU: "Austrália",
  BE: "Bélgica",
  BR: "Brasil",
  CA: "Canadá",
  CH: "Suíça",
  CL: "Chile",
  CN: "China",
  CO: "Colômbia",
  CZ: "República Tcheca",
  DE: "Alemanha",
  DK: "Dinamarca",
  ES: "Espanha",
  FI: "Finlândia",
  FR: "França",
  GB: "Reino Unido",
  GR: "Grécia",
  HK: "Hong Kong",
  HU: "Hungria",
  ID: "Indonésia",
  IE: "Irlanda",
  IL: "Israel",
  IN: "Índia",
  IS: "Islândia",
  IT: "Itália",
  JP: "Japão",
  KR: "Coreia do Sul",
  KY: "Ilhas Cayman",
  LU: "Luxemburgo",
  MX: "México",
  MY: "Malásia",
  NL: "Holanda",
  NO: "Noruega",
  NZ: "Nova Zelândia",
  PE: "Peru",
  PH: "Filipinas",
  PL: "Polônia",
  PT: "Portugal",
  RU: "Rússia",
  SA: "Arábia Saudita",
  SE: "Suécia",
  SG: "Singapura",
  TH: "Tailândia",
  TR: "Turquia",
  TW: "Taiwan",
  US: "Estados Unidos",
  ZA: "África do Sul",
};

const COUNTRY_LABELS_BY_LOCALE: Record<string, Record<string, string>> = {
  en: EN_COUNTRY_LABELS,
  pt: PT_COUNTRY_LABELS,
};

export function translateCountry(isoCode: string, locale: string): string {
  const normalized = isoCode.trim().toUpperCase();
  const dictionary =
    COUNTRY_LABELS_BY_LOCALE[locale] ?? EN_COUNTRY_LABELS;
  return dictionary[normalized] ?? EN_COUNTRY_LABELS[normalized] ?? normalized;
}
