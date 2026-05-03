import { describe, it, expect } from "vitest";
import { CANONICAL_SECTORS, SECTOR_LABELS, translateSector } from "./sectorLabels";

const SUPPORTED_NON_ENGLISH_LOCALES = ["pt", "es", "zh", "fr", "de", "it"] as const;

describe("translateSector", () => {
  it("returns the Portuguese translation for known sectors in pt", () => {
    expect(translateSector("Technology", "pt")).toBe("Tecnologia");
    expect(translateSector("Health Services", "pt")).toBe("Saúde");
    expect(translateSector("Finance", "pt")).toBe("Financeiro");
  });

  it("returns the English value as-is in en", () => {
    expect(translateSector("Technology", "en")).toBe("Technology");
    expect(translateSector("Health Services", "en")).toBe("Health Services");
  });

  it("returns the Spanish translation for known sectors in es", () => {
    expect(translateSector("Technology", "es")).toBe("Tecnología");
    expect(translateSector("Healthcare", "es")).toBe("Salud");
    expect(translateSector("Real Estate", "es")).toBe("Inmobiliario");
  });

  it("returns the Chinese translation for known sectors in zh", () => {
    expect(translateSector("Technology", "zh")).toBe("科技");
    expect(translateSector("Energy", "zh")).toBe("能源");
  });

  it("returns the French translation for known sectors in fr", () => {
    expect(translateSector("Technology", "fr")).toBe("Technologie");
    expect(translateSector("Healthcare", "fr")).toBe("Santé");
  });

  it("returns the German translation for known sectors in de", () => {
    expect(translateSector("Technology", "de")).toBe("Technologie");
    expect(translateSector("Energy Minerals", "de")).toBe("Energierohstoffe");
  });

  it("returns the Italian translation for known sectors in it", () => {
    expect(translateSector("Technology", "it")).toBe("Tecnologia");
    expect(translateSector("Healthcare", "it")).toBe("Sanità");
  });

  it("falls back to the English value for unsupported locales", () => {
    expect(translateSector("Technology", "ja")).toBe("Technology");
    expect(translateSector("Energy Minerals", "ko")).toBe("Energy Minerals");
  });

  it("falls back to the input when the sector is unknown", () => {
    expect(translateSector("MysteryNewSector", "pt")).toBe("MysteryNewSector");
    expect(translateSector("MysteryNewSector", "en")).toBe("MysteryNewSector");
  });

  describe.each(SUPPORTED_NON_ENGLISH_LOCALES)(
    "locale %s",
    (locale) => {
      it.each(CANONICAL_SECTORS)(
        `has a non-empty entry for %s`,
        (sector) => {
          const entry = SECTOR_LABELS[sector][locale];
          expect(entry).toBeDefined();
          expect(entry.length).toBeGreaterThan(0);
        },
      );
    },
  );
});
