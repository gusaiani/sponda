import { useTranslation } from "../i18n";

interface YearsSliderProps {
  years: number;
  maxYears: number;
  onYearsChange: (years: number) => void;
}

const TERM_LABEL: Record<string, string> = {
  pt: "PRAZO:", en: "TERM:", es: "PLAZO:", zh: "期限:", fr: "DURÉE:", de: "ZEITRAUM:", it: "PERIODO:",
};

const YEARS_LABEL: Record<string, string> = {
  pt: "ANOS", en: "YEARS", es: "AÑOS", zh: "年", fr: "ANS", de: "JAHRE", it: "ANNI",
};

export function YearsSlider({ years, maxYears, onYearsChange }: YearsSliderProps) {
  const { locale } = useTranslation();

  if (maxYears <= 1) return null;

  return (
    <div className="years-slider" data-years={years}>
      <span className="years-slider-label">{TERM_LABEL[locale] || TERM_LABEL.en}</span>
      <div className="years-slider-track">
        <span className="years-slider-bound">1</span>
        <div className="years-slider-input-wrapper">
          <span className="years-slider-current" style={{ left: `calc(7px + ${((years - 1) / (maxYears - 1)) * 100}% - ${((years - 1) / (maxYears - 1)) * 14}px)` }}>{years}</span>
          <input
            id="years-range"
            type="range"
            min={1}
            max={maxYears}
            step={1}
            value={years}
            onChange={(e) => onYearsChange(Number(e.target.value))}
            className="years-slider-input"
          />
        </div>
        <span className="years-slider-bound">{maxYears}</span>
      </div>
      <span className="years-slider-label">{YEARS_LABEL[locale] || YEARS_LABEL.en}</span>
    </div>
  );
}
