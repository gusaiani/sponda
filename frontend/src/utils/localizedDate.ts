/**
 * Typed dates in the order the active locale writes them: dd/mm/aaaa in
 * Portuguese, mm/dd/yyyy in English, TT.MM.JJJJ in German. The order and the
 * separator come from Intl, so they match `formatCalendarDate`.
 */

export type DatePart = "day" | "month" | "year";

export interface DateFieldLayout {
  order: DatePart[];
  separator: string;
}

const DIGITS_PER_PART: Record<DatePart, number> = { day: 2, month: 2, year: 4 };
export const DIGITS_IN_FULL_DATE = 8;
const LAYOUT_SAMPLE_DATE = new Date(Date.UTC(2026, 10, 3));

const layoutCache = new Map<string, DateFieldLayout>();

export function dateFieldLayout(locale: string): DateFieldLayout {
  const cached = layoutCache.get(locale);
  if (cached) return cached;

  const parts = new Intl.DateTimeFormat(locale, {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    timeZone: "UTC",
  }).formatToParts(LAYOUT_SAMPLE_DATE);

  const order = parts
    .map((part) => part.type)
    .filter((type): type is DatePart => type === "day" || type === "month" || type === "year");
  const separator = parts.find((part) => part.type === "literal")?.value.trim() || "/";

  const layout = { order, separator };
  layoutCache.set(locale, layout);
  return layout;
}

/** Keep the digits, cap them at a full date, and place the separators. */
export function maskDateDigits(input: string, locale: string): string {
  const { order, separator } = dateFieldLayout(locale);
  let remaining = input.replace(/\D/g, "").slice(0, DIGITS_IN_FULL_DATE);
  const groups: string[] = [];

  for (const part of order) {
    if (!remaining) break;
    groups.push(remaining.slice(0, DIGITS_PER_PART[part]));
    remaining = remaining.slice(DIGITS_PER_PART[part]);
  }
  return groups.join(separator);
}

/** "12/11/2026" in pt → "2026-11-12". Null when incomplete or not a real day. */
export function parseLocalizedDate(text: string, locale: string): string | null {
  const digits = text.replace(/\D/g, "");
  if (digits.length !== DIGITS_IN_FULL_DATE) return null;

  const { order } = dateFieldLayout(locale);
  const values: Partial<Record<DatePart, number>> = {};
  let offset = 0;
  for (const part of order) {
    values[part] = Number(digits.slice(offset, offset + DIGITS_PER_PART[part]));
    offset += DIGITS_PER_PART[part];
  }

  const { year = 0, month = 0, day = 0 } = values;
  const candidate = new Date(Date.UTC(year, month - 1, day));
  const isRealDay =
    candidate.getUTCFullYear() === year &&
    candidate.getUTCMonth() === month - 1 &&
    candidate.getUTCDate() === day;
  if (!isRealDay) return null;

  return `${String(year).padStart(4, "0")}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}
