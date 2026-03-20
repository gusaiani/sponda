/** Map backend labels (PE10, PFCF7…) to Portuguese equivalents */
export function ptLabel(label: string): string {
  return label.replace(/^PE/, "P/L").replace(/^PFCF/, "P/FCL");
}

/** Replace decimal dot with comma for Brazilian notation */
export function br(n: number, digits: number): string {
  return n.toFixed(digits).replace(".", ",");
}

export function formatLargeNumber(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 1e9) return `R$ ${br(value / 1e9, 2)}B`;
  if (abs >= 1e6) return `R$ ${br(value / 1e6, 2)}M`;
  if (abs >= 1e3) return `R$ ${br(value / 1e3, 1)}K`;
  return `R$ ${br(value, 0)}`;
}

export function formatQuarterLabel(dateStr: string): string {
  const [year, month] = dateStr.split("-").map(Number);
  const q = Math.ceil(month / 3);
  return `${q}T${year}`;
}
