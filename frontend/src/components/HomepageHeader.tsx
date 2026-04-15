"use client";

import { useTranslation } from "../i18n";
import { YearsSlider } from "./YearsSlider";

interface HomepageHeaderProps {
  isAuthenticated: boolean;
  favoriteCount: number;
  listCount: number;
  years: number;
  maxYears: number;
  onYearsChange: (years: number) => void;
}

export function shouldShowEmptyFavoritesCta({
  isAuthenticated,
  favoriteCount,
  listCount,
}: {
  isAuthenticated: boolean;
  favoriteCount: number;
  listCount: number;
}): boolean {
  if (!isAuthenticated) return true;
  return favoriteCount === 0 && listCount === 0;
}

function SpondaCircleLogo() {
  return (
    <svg
      className="homepage-header-logo-svg"
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 32 32"
      aria-hidden="true"
    >
      <circle cx="16" cy="16" r="16" fill="#1b347e" />
      <line x1="16" y1="2" x2="16" y2="7" stroke="#fff" strokeWidth="1.5" strokeLinecap="round" />
      <line x1="16" y1="25" x2="16" y2="30" stroke="#fff" strokeWidth="1.5" strokeLinecap="round" />
      <text
        x="16"
        y="21.5"
        fontFamily="Satoshi,system-ui,sans-serif"
        fontSize="18"
        fontWeight="500"
        fill="#fff"
        textAnchor="middle"
      >
        S
      </text>
    </svg>
  );
}

export function HomepageHeader({
  isAuthenticated,
  favoriteCount,
  listCount,
  years,
  maxYears,
  onYearsChange,
}: HomepageHeaderProps) {
  const { t } = useTranslation();

  const showEmptyCta = shouldShowEmptyFavoritesCta({
    isAuthenticated,
    favoriteCount,
    listCount,
  });
  const headline = showEmptyCta
    ? t("homepage.favorites_empty_cta")
    : t("homepage.your_favorites");

  return (
    <div className="homepage-header">
      <div className="homepage-header-left">
        <span className="homepage-header-logo">
          <SpondaCircleLogo />
        </span>
        <h2 className="homepage-header-name">{headline}</h2>
      </div>
      {maxYears > 1 && (
        <div className="homepage-header-slider">
          <YearsSlider years={years} maxYears={maxYears} onYearsChange={onYearsChange} />
        </div>
      )}
    </div>
  );
}
