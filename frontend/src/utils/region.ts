const BRAZILIAN_TIMEZONES = new Set([
  "America/Sao_Paulo",
  "America/Fortaleza",
  "America/Recife",
  "America/Bahia",
  "America/Belem",
  "America/Maceio",
  "America/Cuiaba",
  "America/Campo_Grande",
  "America/Manaus",
  "America/Porto_Velho",
  "America/Boa_Vista",
  "America/Santarem",
  "America/Rio_Branco",
  "America/Araguaina",
  "America/Noronha",
  "America/Eirunepe",
]);

export type Region = "brazil" | "us" | "europe" | "asia";

export function detectRegion(): Region {
  if (typeof Intl === "undefined") return "brazil";

  try {
    const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    if (BRAZILIAN_TIMEZONES.has(timezone)) return "brazil";
    if (timezone.startsWith("Europe/")) return "europe";
    if (timezone.startsWith("Asia/") || timezone.startsWith("Australia/") || timezone.startsWith("Pacific/")) return "asia";
  } catch {
    return "brazil";
  }

  return "us";
}
