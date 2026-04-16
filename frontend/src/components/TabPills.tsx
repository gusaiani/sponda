"use client";

import Link from "next/link";
import { buildTabPath, type TabKey } from "../utils/tabs";
import { useTranslation } from "../i18n";
import type { TranslationKey } from "../i18n/types";

interface TabPillsProps {
  ticker: string;
  activeTab: TabKey;
  onPrefetch?: (tab: TabKey) => void;
}

const TABS: { key: TabKey; labelKey: TranslationKey; prefetchable: boolean }[] = [
  { key: "metrics", labelKey: "tabs.metrics", prefetchable: false },
  { key: "fundamentals", labelKey: "tabs.fundamentals", prefetchable: true },
  { key: "compare", labelKey: "tabs.compare", prefetchable: false },
  { key: "charts", labelKey: "tabs.charts", prefetchable: true },
];

export function TabPills({ ticker, activeTab, onPrefetch }: TabPillsProps) {
  const { t, locale } = useTranslation();
  return (
    <div className="tabs-desktop">
      {TABS.map((tab) => (
        <Link
          key={tab.key}
          href={buildTabPath(locale, ticker, tab.key)}
          className={`tab-pill ${activeTab === tab.key ? "tab-pill-active" : ""}`}
          onMouseEnter={
            tab.prefetchable && onPrefetch ? () => onPrefetch(tab.key) : undefined
          }
        >
          {t(tab.labelKey)}
        </Link>
      ))}
    </div>
  );
}
