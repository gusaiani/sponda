const MONTH_NAMES_PT = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
const MONTH_NAMES_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** Convert an ISO-style date string ("2024-01-31") to "jan/24" (pt) or "Jan/24" (en). */
export function formatPriceDate(dateString: string, dateLocale: string = "pt"): string {
  const months = dateLocale === "pt" ? MONTH_NAMES_PT : MONTH_NAMES_EN;
  const [year, month] = dateString.split("-");
  return `${months[parseInt(month, 10) - 1]}/${year.slice(2)}`;
}
