import { useEffect, useState } from "react";

const FONTS = [
  // — Google Fonts (curated) —
  { family: "Abril Fatface", weight: 400, src: "Google" },
  { family: "Bodoni Moda", weight: 400, src: "Google" },
  { family: "Bodoni Moda", weight: 700, src: "Google" },
  { family: "Bodoni Moda", weight: 900, src: "Google" },
  { family: "Playfair Display", weight: 400, src: "Google" },
  { family: "Playfair Display", weight: 700, src: "Google" },
  { family: "Playfair Display", weight: 900, src: "Google" },
  { family: "Playfair Display SC", weight: 400, src: "Google" },
  { family: "Playfair Display SC", weight: 900, src: "Google" },
  { family: "Cinzel", weight: 400, src: "Google" },
  { family: "Cinzel", weight: 700, src: "Google" },
  { family: "Cinzel", weight: 900, src: "Google" },
  { family: "Cormorant", weight: 500, src: "Google" },
  { family: "Cormorant", weight: 700, src: "Google" },
  { family: "Cormorant Garamond", weight: 500, src: "Google" },
  { family: "Cormorant Garamond", weight: 700, src: "Google" },
  { family: "Cormorant SC", weight: 500, src: "Google" },
  { family: "Cormorant SC", weight: 700, src: "Google" },
  { family: "Cormorant Unicase", weight: 500, src: "Google" },
  { family: "Cormorant Unicase", weight: 700, src: "Google" },
  { family: "EB Garamond", weight: 400, src: "Google" },
  { family: "EB Garamond", weight: 700, src: "Google" },
  { family: "Crimson Pro", weight: 500, src: "Google" },
  { family: "Crimson Pro", weight: 800, src: "Google" },
  { family: "DM Serif Display", weight: 400, src: "Google" },
  { family: "DM Serif Text", weight: 400, src: "Google" },
  { family: "Libre Baskerville", weight: 400, src: "Google" },
  { family: "Libre Baskerville", weight: 700, src: "Google" },
  { family: "Libre Caslon Display", weight: 400, src: "Google" },
  { family: "Lora", weight: 500, src: "Google" },
  { family: "Lora", weight: 700, src: "Google" },
  { family: "Merriweather", weight: 700, src: "Google" },
  { family: "Merriweather", weight: 900, src: "Google" },
  { family: "Noto Serif Display", weight: 500, src: "Google" },
  { family: "Noto Serif Display", weight: 800, src: "Google" },
  { family: "Old Standard TT", weight: 400, src: "Google" },
  { family: "Old Standard TT", weight: 700, src: "Google" },
  { family: "Prata", weight: 400, src: "Google" },
  { family: "Source Serif 4", weight: 500, src: "Google" },
  { family: "Source Serif 4", weight: 800, src: "Google" },
  { family: "Spectral", weight: 500, src: "Google" },
  { family: "Spectral", weight: 700, src: "Google" },
  { family: "Spectral SC", weight: 500, src: "Google" },
  { family: "Spectral SC", weight: 700, src: "Google" },
  { family: "Gloock", weight: 400, src: "Google" },
  { family: "Young Serif", weight: 400, src: "Google" },
  { family: "Instrument Serif", weight: 400, src: "Google" },
  { family: "Baskervville", weight: 400, src: "Google" },
  { family: "Rufina", weight: 400, src: "Google" },
  { family: "Rufina", weight: 700, src: "Google" },
  { family: "Vidaloka", weight: 400, src: "Google" },
  { family: "Vollkorn SC", weight: 600, src: "Google" },
  { family: "Vollkorn SC", weight: 900, src: "Google" },
  { family: "Cardo", weight: 400, src: "Google" },
  { family: "Cardo", weight: 700, src: "Google" },
  { family: "Gilda Display", weight: 400, src: "Google" },
  { family: "Forum", weight: 400, src: "Google" },
  { family: "Marcellus", weight: 400, src: "Google" },
  { family: "Marcellus SC", weight: 400, src: "Google" },
  { family: "Brygada 1918", weight: 500, src: "Google" },
  { family: "Brygada 1918", weight: 700, src: "Google" },
  { family: "Literata", weight: 500, src: "Google" },
  { family: "Literata", weight: 700, src: "Google" },
  { family: "Fraunces", weight: 400, src: "Google" },
  { family: "Fraunces", weight: 700, src: "Google" },
  { family: "Fraunces", weight: 900, src: "Google" },
  { family: "Newsreader", weight: 400, src: "Google" },
  { family: "Newsreader", weight: 700, src: "Google" },
  { family: "Eczar", weight: 500, src: "Google" },
  { family: "Eczar", weight: 700, src: "Google" },
  { family: "Inknut Antiqua", weight: 400, src: "Google" },
  { family: "Inknut Antiqua", weight: 700, src: "Google" },
  { family: "Arapey", weight: 400, src: "Google" },
  { family: "Bellefair", weight: 400, src: "Google" },
  { family: "Vesper Libre", weight: 400, src: "Google" },
  { family: "Vesper Libre", weight: 900, src: "Google" },
  // — FontShare (Indian Type Foundry) —
  { family: "Zodiak", weight: 400, src: "FontShare" },
  { family: "Zodiak", weight: 700, src: "FontShare" },
  { family: "Gambetta", weight: 400, src: "FontShare" },
  { family: "Gambetta", weight: 700, src: "FontShare" },
  { family: "Sentient", weight: 400, src: "FontShare" },
  { family: "Sentient", weight: 700, src: "FontShare" },
  { family: "Erode", weight: 400, src: "FontShare" },
  { family: "Erode", weight: 700, src: "FontShare" },
  { family: "Boska", weight: 400, src: "FontShare" },
  { family: "Boska", weight: 700, src: "FontShare" },
  { family: "Bespoke Serif", weight: 400, src: "FontShare" },
  { family: "Bespoke Serif", weight: 700, src: "FontShare" },
  { family: "Tanker", weight: 400, src: "FontShare" },
  { family: "Author", weight: 400, src: "FontShare" },
  { family: "Author", weight: 700, src: "FontShare" },
  { family: "Sharpie", weight: 400, src: "FontShare" },
  { family: "Sharpie", weight: 700, src: "FontShare" },
  { family: "Ranade", weight: 400, src: "FontShare" },
  { family: "Ranade", weight: 700, src: "FontShare" },
  { family: "Satoshi", weight: 500, src: "FontShare" },
  { family: "Satoshi", weight: 700, src: "FontShare" },
];

export function FontPickerLogo() {
  const [index, setIndex] = useState(0);
  const font = FONTS[index];

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "ArrowRight") {
        e.preventDefault();
        setIndex((i) => (i + 1) % FONTS.length);
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        setIndex((i) => (i - 1 + FONTS.length) % FONTS.length);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div style={{ textAlign: "center" }}>
      <div
        style={{
          fontFamily: `"${font.family}", serif`,
          fontWeight: font.weight,
          fontSize: 30,
          color: "#1a2a5a",
          lineHeight: 1,
          marginBottom: 4,
        }}
      >
        SPONDA
      </div>
      <div
        style={{
          position: "fixed",
          bottom: 12,
          right: 16,
          fontSize: 11,
          color: "#999",
          letterSpacing: 1,
          fontFamily: "system-ui, sans-serif",
          zIndex: 9999,
        }}
      >
        {font.family} {font.weight} — {font.src} — {index + 1}/{FONTS.length} — ← →
      </div>
    </div>
  );
}
