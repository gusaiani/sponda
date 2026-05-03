/** Localized labels for the sector strings the backend returns
 * (English-canonical, sourced from FMP / TradingView's industry taxonomy).
 *
 * Lives outside the main i18n dictionary because the sector universe grows
 * as new exchanges are onboarded and we'd rather extend a small map than
 * touch every locale file each time. Locales without an entry fall back to
 * the canonical English value.
 */
const PT_SECTOR_LABELS: Record<string, string> = {
  "Commercial Services": "Serviços Comerciais",
  "Communications": "Comunicações",
  "Consumer Durables": "Bens de Consumo Duráveis",
  "Consumer Non-Durables": "Bens de Consumo Não Duráveis",
  "Consumer Services": "Serviços ao Consumidor",
  "Distribution Services": "Serviços de Distribuição",
  "Electronic Technology": "Tecnologia Eletrônica",
  "Energy Minerals": "Minerais Energéticos",
  "Finance": "Financeiro",
  "Financial Services": "Serviços Financeiros",
  "Health Services": "Saúde",
  "Health Technology": "Tecnologia da Saúde",
  "Industrial Services": "Serviços Industriais",
  "Miscellaneous": "Diversos",
  "Non-Energy Minerals": "Minerais Não Energéticos",
  "Process Industries": "Indústrias de Processo",
  "Producer Manufacturing": "Manufatura",
  "Retail Trade": "Varejo",
  "Technology": "Tecnologia",
  "Technology Services": "Serviços de Tecnologia",
  "Transportation": "Transporte",
  "Utilities": "Utilidades",
};

const SECTOR_LABELS_BY_LOCALE: Record<string, Record<string, string>> = {
  pt: PT_SECTOR_LABELS,
};

export function translateSector(sector: string, locale: string): string {
  const dictionary = SECTOR_LABELS_BY_LOCALE[locale];
  return dictionary?.[sector] ?? sector;
}
