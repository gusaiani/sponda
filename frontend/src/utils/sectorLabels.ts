/** Localized labels for the sector strings the backend returns
 * (English-canonical, sourced from a mix of FMP, Yahoo, and TradingView
 * taxonomies — that's why "Healthcare" and "Health Services" both appear).
 *
 * Lives outside the main i18n dictionary because the sector universe grows
 * as new exchanges are onboarded and we'd rather extend a small map than
 * touch every locale file each time. Locales without a translation for
 * a given sector fall back to the canonical English value.
 */
type SupportedLocale = "pt" | "es" | "zh" | "fr" | "de" | "it";

export const SECTOR_LABELS: Record<string, Record<SupportedLocale, string>> = {
  "Basic Materials": {
    pt: "Materiais Básicos",
    es: "Materiales Básicos",
    zh: "基础材料",
    fr: "Matériaux de Base",
    de: "Grundstoffe",
    it: "Materiali di Base",
  },
  "Commercial Services": {
    pt: "Serviços Comerciais",
    es: "Servicios Comerciales",
    zh: "商业服务",
    fr: "Services Commerciaux",
    de: "Gewerbliche Dienstleistungen",
    it: "Servizi Commerciali",
  },
  "Communication Services": {
    pt: "Serviços de Comunicação",
    es: "Servicios de Comunicación",
    zh: "通信服务",
    fr: "Services de Communication",
    de: "Kommunikationsdienste",
    it: "Servizi di Comunicazione",
  },
  "Communications": {
    pt: "Comunicações",
    es: "Comunicaciones",
    zh: "通信",
    fr: "Communications",
    de: "Kommunikation",
    it: "Comunicazioni",
  },
  "Consumer Cyclical": {
    pt: "Consumo Cíclico",
    es: "Consumo Cíclico",
    zh: "周期性消费",
    fr: "Consommation Cyclique",
    de: "Zyklischer Konsum",
    it: "Consumi Ciclici",
  },
  "Consumer Defensive": {
    pt: "Consumo Defensivo",
    es: "Consumo Defensivo",
    zh: "防御性消费",
    fr: "Consommation Défensive",
    de: "Defensiver Konsum",
    it: "Consumi Difensivi",
  },
  "Consumer Durables": {
    pt: "Bens de Consumo Duráveis",
    es: "Bienes de Consumo Duraderos",
    zh: "耐用消费品",
    fr: "Biens de Consommation Durables",
    de: "Langlebige Konsumgüter",
    it: "Beni di Consumo Durevoli",
  },
  "Consumer Non-Durables": {
    pt: "Bens de Consumo Não Duráveis",
    es: "Bienes de Consumo No Duraderos",
    zh: "非耐用消费品",
    fr: "Biens de Consommation Non Durables",
    de: "Nicht-langlebige Konsumgüter",
    it: "Beni di Consumo Non Durevoli",
  },
  "Consumer Services": {
    pt: "Serviços ao Consumidor",
    es: "Servicios al Consumidor",
    zh: "消费者服务",
    fr: "Services aux Consommateurs",
    de: "Konsumentendienstleistungen",
    it: "Servizi ai Consumatori",
  },
  "Distribution Services": {
    pt: "Serviços de Distribuição",
    es: "Servicios de Distribución",
    zh: "分销服务",
    fr: "Services de Distribution",
    de: "Vertriebsdienstleistungen",
    it: "Servizi di Distribuzione",
  },
  "Electronic Technology": {
    pt: "Tecnologia Eletrônica",
    es: "Tecnología Electrónica",
    zh: "电子技术",
    fr: "Technologie Électronique",
    de: "Elektroniktechnologie",
    it: "Tecnologia Elettronica",
  },
  "Energy": {
    pt: "Energia",
    es: "Energía",
    zh: "能源",
    fr: "Énergie",
    de: "Energie",
    it: "Energia",
  },
  "Energy Minerals": {
    pt: "Minerais Energéticos",
    es: "Minerales Energéticos",
    zh: "能源矿产",
    fr: "Minéraux Énergétiques",
    de: "Energierohstoffe",
    it: "Minerali Energetici",
  },
  "Finance": {
    pt: "Financeiro",
    es: "Finanzas",
    zh: "金融",
    fr: "Finance",
    de: "Finanzen",
    it: "Finanza",
  },
  "Financial Services": {
    pt: "Serviços Financeiros",
    es: "Servicios Financieros",
    zh: "金融服务",
    fr: "Services Financiers",
    de: "Finanzdienstleistungen",
    it: "Servizi Finanziari",
  },
  "Health Services": {
    pt: "Saúde",
    es: "Salud",
    zh: "健康服务",
    fr: "Services de Santé",
    de: "Gesundheitsdienste",
    it: "Servizi Sanitari",
  },
  "Health Technology": {
    pt: "Tecnologia da Saúde",
    es: "Tecnología de la Salud",
    zh: "健康技术",
    fr: "Technologie de la Santé",
    de: "Gesundheitstechnologie",
    it: "Tecnologia Sanitaria",
  },
  "Healthcare": {
    pt: "Saúde",
    es: "Salud",
    zh: "医疗保健",
    fr: "Santé",
    de: "Gesundheitswesen",
    it: "Sanità",
  },
  "Industrial Services": {
    pt: "Serviços Industriais",
    es: "Servicios Industriales",
    zh: "工业服务",
    fr: "Services Industriels",
    de: "Industriedienstleistungen",
    it: "Servizi Industriali",
  },
  "Industrials": {
    pt: "Industriais",
    es: "Industriales",
    zh: "工业",
    fr: "Industries",
    de: "Industrie",
    it: "Industriali",
  },
  "Miscellaneous": {
    pt: "Diversos",
    es: "Varios",
    zh: "综合",
    fr: "Divers",
    de: "Sonstiges",
    it: "Vari",
  },
  "Non-Energy Minerals": {
    pt: "Minerais Não Energéticos",
    es: "Minerales No Energéticos",
    zh: "非能源矿产",
    fr: "Minéraux Non Énergétiques",
    de: "Nicht-energetische Rohstoffe",
    it: "Minerali Non Energetici",
  },
  "Process Industries": {
    pt: "Indústrias de Processo",
    es: "Industrias de Procesos",
    zh: "流程工业",
    fr: "Industries de Process",
    de: "Prozessindustrie",
    it: "Industrie di Processo",
  },
  "Producer Manufacturing": {
    pt: "Manufatura",
    es: "Manufactura",
    zh: "生产制造",
    fr: "Fabrication Industrielle",
    de: "Produzierendes Gewerbe",
    it: "Manifatturiero",
  },
  "Real Estate": {
    pt: "Imobiliário",
    es: "Inmobiliario",
    zh: "房地产",
    fr: "Immobilier",
    de: "Immobilien",
    it: "Immobiliare",
  },
  "Retail Trade": {
    pt: "Varejo",
    es: "Comercio Minorista",
    zh: "零售贸易",
    fr: "Commerce de Détail",
    de: "Einzelhandel",
    it: "Commercio al Dettaglio",
  },
  "Technology": {
    pt: "Tecnologia",
    es: "Tecnología",
    zh: "科技",
    fr: "Technologie",
    de: "Technologie",
    it: "Tecnologia",
  },
  "Technology Services": {
    pt: "Serviços de Tecnologia",
    es: "Servicios Tecnológicos",
    zh: "科技服务",
    fr: "Services Technologiques",
    de: "Technologiedienste",
    it: "Servizi Tecnologici",
  },
  "Transportation": {
    pt: "Transporte",
    es: "Transporte",
    zh: "运输",
    fr: "Transport",
    de: "Transport",
    it: "Trasporti",
  },
  "Utilities": {
    pt: "Utilidades",
    es: "Servicios Públicos",
    zh: "公用事业",
    fr: "Services Publics",
    de: "Versorger",
    it: "Servizi Pubblici",
  },
};

/** Canonical English sector list — every sector the screener can show
 * a localized label for. Exported so tests can verify each supported
 * locale covers the full set without ad-hoc enumeration. */
export const CANONICAL_SECTORS = Object.keys(SECTOR_LABELS);

export function translateSector(sector: string, locale: string): string {
  const localized = SECTOR_LABELS[sector]?.[locale as SupportedLocale];
  return localized ?? sector;
}
