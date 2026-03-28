export type TabKey = "metrics" | "charts" | "fundamentals" | "compare";

export const TAB_PATHS: Record<string, TabKey> = {
  graficos: "charts",
  fundamentos: "fundamentals",
  comparar: "compare",
};

export const TAB_TO_SUFFIX: Record<TabKey, string> = {
  metrics: "",
  charts: "/graficos",
  fundamentals: "/fundamentos",
  compare: "/comparar",
};

export const TAB_LABELS: Record<TabKey, string> = {
  metrics: "Indicadores",
  fundamentals: "Fundamentos",
  compare: "Comparar",
  charts: "Gráficos",
};

export function resolveTab(pathname: string): TabKey {
  const lastSegment = pathname.split("/").filter(Boolean).pop() ?? "";
  if (TAB_PATHS[lastSegment]) return TAB_PATHS[lastSegment];
  return "metrics";
}

export function buildTabPath(ticker: string, tab: TabKey): string {
  return `/${ticker}${TAB_TO_SUFFIX[tab]}`;
}
