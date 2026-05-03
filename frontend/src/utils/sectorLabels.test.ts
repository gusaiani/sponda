import { describe, it, expect } from "vitest";
import { translateSector } from "./sectorLabels";

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

  it("falls back to the English value when no translation exists for the locale", () => {
    expect(translateSector("Technology", "fr")).toBe("Technology");
    expect(translateSector("Energy Minerals", "de")).toBe("Energy Minerals");
  });

  it("falls back to the input when the sector is unknown", () => {
    expect(translateSector("MysteryNewSector", "pt")).toBe("MysteryNewSector");
    expect(translateSector("MysteryNewSector", "en")).toBe("MysteryNewSector");
  });
});
