"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useParams, usePathname, useRouter } from "next/navigation";
import Link from "next/link";
import dynamic from "next/dynamic";
const CompanyMetricsCard = dynamic(
  () => import("../../../components/CompanyMetricsCard").then((mod) => mod.CompanyMetricsCard),
  { ssr: false }
);
const MultiplesChart = dynamic(
  () => import("../../../components/MultiplesChart").then((mod) => mod.MultiplesChart),
  { ssr: false }
);

function CompanyMetricsCardLoading() {
  return (
    <div className="pe10-loading">
      <div className="pe10-loading-bar" />
      <div className="pe10-loading-bar-lg" />
      <div className="pe10-loading-bar-row">
        <div className="pe10-loading-bar-sm" />
        <div className="pe10-loading-bar-sm" />
        <div className="pe10-loading-bar-sm" />
      </div>
    </div>
  );
}

function MultiplesChartLoading() {
  return (
    <div className="chart-loading">
      <div className="chart-loading-bar" />
      <div className="chart-loading-bar-sm" />
    </div>
  );
}

const CompareTab = dynamic(
  () => import("../../../components/CompareTab").then((mod) => mod.CompareTab),
  { ssr: false }
);
const FundamentalsTab = dynamic(
  () => import("../../../components/FundamentalsTab").then((mod) => mod.FundamentalsTab),
  { ssr: false }
);
const CompanyAnalysis = dynamic(
  () => import("../../../components/CompanyAnalysis").then((mod) => mod.CompanyAnalysis),
  { ssr: false }
);
import { FavoriteButton } from "../../../components/FavoriteButton";
import { VisitedButton } from "../../../components/VisitedButton";
import { RevisitBanner } from "../../../components/RevisitBanner";
import { ShareButtons } from "../../../components/ShareButtons";
import { CompanyGradeCard } from "../../../components/CompanyGradeCard";
import { useLearningMode } from "../../../learning";
import {
  usePE10,
  fetchQuote,
  resolveLookupLimitAction,
  type QuoteResult,
} from "../../../hooks/usePE10";
import { AuthModal } from "../../../components/AuthModal";
import { setEmailVerificationPromptVisible } from "../../../utils/emailVerificationPrompt";
import { useTickerDetail } from "../../../hooks/useTickerDetail";
import { usePeers } from "../../../hooks/usePeers";
import { useMultiplesHistory, fetchMultiplesHistory } from "../../../hooks/useMultiplesHistory";
import { deriveForYears } from "../../../hooks/deriveForYears";
import { useSetAssistantWindow } from "../../../components/assistant/AssistantWindowContext";
import { fetchFundamentals, useFundamentals } from "../../../hooks/useFundamentals";
import { useSavedLists } from "../../../hooks/useSavedLists";
import { logoUrl, currencyCode } from "../../../utils/format";
import { useTranslation } from "../../../i18n";
import { YearsSlider } from "../../../components/YearsSlider";
import { InflationToggle, type InflationMode } from "../../../components/InflationToggle";
import { TabPills } from "../../../components/TabPills";
import { ListHeader } from "../../../components/ListHeader";
import { SpondsTab } from "../../../components/social/SpondsTab";

const STALE_TIME = 30 * 60 * 1000;

const DEFAULT_YEARS = 10;
// The widest window the backend computes (PE_WINDOW_MAX_YEARS). A saved list
// spans it in full: the company in the URL is only the address the table is
// served from, so its own history must not cap the list's slider.
const LIST_MAX_YEARS = 15;

import { resolveTab, buildTabPath, type TabKey } from "../../../utils/tabs";

interface TickerPageClientProps {
  initialData?: QuoteResult | null;
}

export function TickerPageClient({ initialData }: TickerPageClientProps) {
  const { t, locale } = useTranslation();
  const { enabled: learningModeEnabled } = useLearningMode();
  const { ticker: rawTicker } = useParams<{ ticker: string }>();
  const upperTicker = (rawTicker || "").toUpperCase();
  const queryClient = useQueryClient();
  const router = useRouter();
  const pathname = usePathname();
  const [years, setYears] = useState(() => {
    if (typeof window === "undefined") return DEFAULT_YEARS;
    const param = new URLSearchParams(window.location.search).get("years");
    if (!param) return DEFAULT_YEARS;
    const parsed = parseInt(param, 10);
    return parsed >= 1 && parsed <= 20 ? parsed : DEFAULT_YEARS;
  });
  const initialWithTickers = (() => {
    if (typeof window === "undefined") return [] as string[];
    const withParam = new URLSearchParams(window.location.search).get("with");
    if (!withParam) return [] as string[];
    return withParam
      .split(",")
      .map((ticker) => ticker.trim().toUpperCase())
      .filter(Boolean);
  })();
  const [compareTickers, setCompareTickers] = useState<string[]>(initialWithTickers);
  const [activeListId, setActiveListId] = useState<number | null>(null);
  // A saved list's own membership, in its own order. Held apart from
  // `compareTickers` because a list is not "this company plus others": the
  // company in the URL is just the address the table is served from, and
  // removing it from the list must not break the page.
  const [listTickers, setListTickers] = useState<string[]>([]);
  const seededForTicker = useRef<string | null>(
    initialWithTickers.length > 0 ? upperTicker : null,
  );

  const activeTab = resolveTab(pathname);
  const tabBarRef = useRef<HTMLDivElement>(null);
  const [sliderFixedTop, setSliderFixedTop] = useState<number | null>(null);
  const [inflationMode, setInflationMode] = useState<InflationMode>("nominal");

  // Deliberately no `isLoading`. React Query reports a pending query as
  // idle, and so not loading, while the persisted cache is being restored,
  // and only the browser restores anything. Gating markup on `isLoading`
  // therefore renders one tree on the server and a different one on the
  // browser's first pass, which is the hydration mismatch behind
  // JAVASCRIPT-NEXTJS-2 and the `removeChild` crash behind
  // JAVASCRIPT-NEXTJS-5. Gate on the data instead: both sides start from
  // exactly what the server fetched.
  const { data: fullData, error } = usePE10(upperTicker, initialData ?? undefined);
  // The company to render, or null while the quote is still missing or the
  // lookup failed. One value, so every section agrees on what is on screen.
  const company = error ? null : fullData ?? null;

  // Daily company-lookup cap hit. Anonymous -> push to sign up via the
  // auth modal; logged-in-but-unverified -> nudge email verification
  // (the auth modal would be wrong, they already have an account).
  const lookupLimit = resolveLookupLimitAction(error);
  const [limitModalDismissed, setLimitModalDismissed] = useState(false);
  const limitModalTicker = useRef<string | null>(null);
  if (limitModalTicker.current !== upperTicker) {
    limitModalTicker.current = upperTicker;
    if (limitModalDismissed) setLimitModalDismissed(false);
  }
  useEffect(() => {
    if (lookupLimit?.kind === "verify-prompt") {
      setEmailVerificationPromptVisible(true);
    }
  }, [lookupLimit?.kind]);

  const { data: currentTicker } = useTickerDetail(upperTicker);
  const { data: peers = [] } = usePeers(upperTicker);
  const { data: fundamentalsData } = useFundamentals(upperTicker, true);
  const { lists } = useSavedLists();
  // The saved list this page is showing, or null when it is showing a
  // company. Every section below asks this one question rather than each
  // re-deriving it from the URL.
  const activeList = activeListId === null
    ? null
    : lists.find((list) => list.id === activeListId) ?? null;

  // Check for listId in URL search params (when opening a saved list)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const listIdParam = params.get("listId");
    if (!listIdParam) return;

    const listId = parseInt(listIdParam, 10);
    const savedList = lists.find((list) => list.id === listId);
    if (!savedList) return;

    // The list's full membership, in the order it was saved. The company in
    // the URL is one member among equals, not the head of the table.
    // Same shape, seeded from a saved list named in the URL: the lists query
    // resolves after the first render and the ref keeps this to once.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setListTickers(savedList.tickers);
    setYears(savedList.years);
    setActiveListId(listId);
    seededForTicker.current = upperTicker;
  }, [lists, upperTicker]);

  // Seed compare list with same-sector peers and prefetch their data
  useEffect(() => {
    if (seededForTicker.current === upperTicker) return;
    if (!peers.length) return;
    if (!fullData) return;

    const peerSymbols = peers.map((peer) => peer.symbol);
    // Seeds the compare list from the sector-peers query the first time it
    // arrives, guarded by a ref so it happens once per ticker. The user edits
    // the list afterwards, so this is state being initialised from a
    // later-arriving source, not a value derived from it.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setCompareTickers(peerSymbols);
    seededForTicker.current = upperTicker;

    for (const peer of peerSymbols) {
      queryClient.prefetchQuery({
        queryKey: ["pe10", peer],
        queryFn: () => fetchQuote(peer),
        staleTime: 30 * 60 * 1000,
      });
    }
  }, [upperTicker, peers, fullData, queryClient]);

  // Lazy: only fetch when charts tab is active
  const { data: historyData, error: historyError } = useMultiplesHistory(
    upperTicker,
    true,
  );

  const companyMaxYears = fullData?.maxYearsAvailable ?? DEFAULT_YEARS;
  const maxYears = activeList ? LIST_MAX_YEARS : companyMaxYears;
  const effectiveYears = Math.min(years, maxYears);

  const derivedData = useMemo(
    () => fullData ? deriveForYears(fullData, effectiveYears) : null,
    [fullData, effectiveYears],
  );

  // Share the active PRAZO window with the floating AssistantBar (it lives in
  // the layout shell, a sibling of this page), so the assistant reasons over
  // the same windowed numbers the user is viewing.
  const setAssistantWindow = useSetAssistantWindow();
  useEffect(() => {
    setAssistantWindow(effectiveYears);
  }, [setAssistantWindow, effectiveYears]);

  // Pin the floating slider to the tab-bar row. The tab bar's Y shifts
  // after first paint (company header mounts when fullData arrives, web
  // fonts swap, cards reflow), so a single mount-time measurement locks
  // in a too-high value. Re-measure after paint and on every reflow of
  // the content above. Document-relative (top + scrollY) so the value is
  // correct even if the page restored a scroll position.
  useEffect(() => {
    const tabBar = tabBarRef.current;
    if (!tabBar) return;

    const measure = () => {
      const rect = tabBar.getBoundingClientRect();
      setSliderFixedTop(rect.top + window.scrollY);
    };

    const raf = requestAnimationFrame(measure);
    window.addEventListener("resize", measure);

    let resizeObserver: ResizeObserver | undefined;
    if (typeof ResizeObserver !== "undefined") {
      resizeObserver = new ResizeObserver(measure);
      resizeObserver.observe(document.body);
    }
    document.fonts?.ready.then(measure).catch(() => {});

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", measure);
      resizeObserver?.disconnect();
    };
  }, [error, fullData, activeTab]);

  function switchTab(tab: TabKey) {
    router.push(buildTabPath(locale, upperTicker, tab));
  }

  function prefetchTabData(tab: TabKey) {
    if (tab === "charts") {
      queryClient.prefetchQuery({
        queryKey: ["multiples-history", upperTicker],
        queryFn: () => fetchMultiplesHistory(upperTicker),
        staleTime: STALE_TIME,
      });
    }
    if (tab === "fundamentals") {
      queryClient.prefetchQuery({
        queryKey: ["fundamentals", upperTicker],
        queryFn: () => fetchFundamentals(upperTicker),
        staleTime: STALE_TIME,
      });
    }
  }


  return (
    <div>

      {/* List header — a saved list stands on its own, with no company
          identity, rating, or currency attached to it. */}
      {activeList && (
        <>
          <ListHeader
            name={activeList.name}
            tickerCount={listTickers.length}
            years={effectiveYears}
          />
          {maxYears > 1 && (
            <div className="years-slider-inline">
              <YearsSlider years={effectiveYears} maxYears={maxYears} onYearsChange={setYears} />
            </div>
          )}
        </>
      )}

      {/* Company header */}
      {company && !activeList && (
        <div className="company-header">
          <div className="company-header-left">
            {company.logo && (
              <img
                className="company-header-logo"
                src={logoUrl(company.ticker)}
                alt={`Logo ${company.name}`}
                loading="lazy"
                onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
              />
            )}
            <h2 className="company-header-name">{company.name} <span className="company-header-ticker">· {upperTicker} · {t("header.currency")}: {
              company.reportedCurrency && company.listingCurrency &&
              company.reportedCurrency !== company.listingCurrency
                ? `${company.listingCurrency} (${t("header.reportsIn")} ${company.reportedCurrency})`
                : currencyCode(upperTicker, company.reportedCurrency)
            }{learningModeEnabled && derivedData?.ratings?.overall != null ? " · " : ""}</span><CompanyGradeCard ratings={derivedData?.ratings ?? null} years={effectiveYears} /></h2>
          </div>
          <div className="company-header-actions">
            <VisitedButton ticker={upperTicker} />
            <FavoriteButton ticker={upperTicker} />
          </div>
        </div>
      )}

      {company && !activeList && <RevisitBanner ticker={upperTicker} />}

      {/* Tab bar: tabs left, years slider floats fixed on the right (desktop) */}
      {company && !activeList && (
        <>
          <div className="tab-bar" ref={tabBarRef}>
            <TabPills
              ticker={upperTicker}
              activeTab={activeTab}
              onPrefetch={prefetchTabData}
            />
          </div>
          <div className="tabs-mobile">
            <select
              className="tabs-dropdown"
              value={activeTab}
              onChange={(e) => switchTab(e.target.value as TabKey)}
            >
              <option value="metrics">{t("tabs.metrics")}</option>
              <option value="fundamentals">{t("tabs.fundamentals")}</option>
              <option value="compare">{t("tabs.compare")}</option>
              <option value="charts">{t("tabs.charts")}</option>
              <option value="sponds">{t("tabs.sponds")}</option>
            </select>
          </div>
          {(activeTab === "metrics" || activeTab === "compare" || activeTab === "fundamentals") && maxYears > 1 && (
            <div className="years-slider-inline years-slider-inline--mobile">
              <YearsSlider years={effectiveYears} maxYears={maxYears} onYearsChange={setYears} />
              {activeTab === "fundamentals" && (
                <InflationToggle
                  mode={inflationMode}
                  onModeChange={setInflationMode}
                  reportedCurrency={fundamentalsData?.reportedCurrency}
                />
              )}
            </div>
          )}
        </>
      )}

      {/* Fixed slider (desktop) */}
      {company && !activeList && (activeTab === "metrics" || activeTab === "compare" || activeTab === "fundamentals") && maxYears > 1 && sliderFixedTop !== null && (
        <div className="years-slider-fixed" style={{ top: sliderFixedTop }}>
          <YearsSlider years={effectiveYears} maxYears={maxYears} onYearsChange={setYears} />
          {activeTab === "fundamentals" && (
            <InflationToggle
              mode={inflationMode}
              onModeChange={setInflationMode}
              reportedCurrency={fundamentalsData?.reportedCurrency}
            />
          )}
        </div>
      )}

      {/* Metrics tab */}
      {activeTab === "metrics" && !activeList && (
        <>
          {!derivedData && !error && <CompanyMetricsCardLoading />}
          {derivedData && (
            <CompanyMetricsCard
              data={derivedData}
              years={effectiveYears}
              maxYears={maxYears}
              onYearsChange={setYears}
              sector={currentTicker?.sector}
              fundamentals={fundamentalsData?.years}
              quarterlyRatios={fundamentalsData?.quarterlyRatios}
              priceHistory={historyData?.prices}
            />
          )}
          {error && (
            <div className="pe10-card">
              <div className="pe10-error">
                {lookupLimit
                  ? `${t("quota.limit_reached")} ${lookupLimit.limit ?? ""} ${
                      locale === "pt" ? "consultas diárias" : "daily queries"
                    }.`
                  : (error as Error).message}
              </div>
            </div>
          )}
        </>
      )}

      {/* Charts tab */}
      {activeTab === "charts" && !activeList && (
        <>
          {!historyData && !historyError && <MultiplesChartLoading />}
          {historyData && <MultiplesChart data={historyData} />}
          {historyError && (
            <div className="chart-container">
              <div className="chart-error">{(historyError as Error).message}</div>
            </div>
          )}
        </>
      )}

      {/* Fundamentals tab */}
      {activeTab === "fundamentals" && !activeList && (
        <FundamentalsTab
          ticker={upperTicker}
          years={effectiveYears}
          valueMode={inflationMode}
          quote={fullData ?? null}
        />
      )}

      {/* Compare tab */}
      {(activeTab === "compare" || activeList) && (
        <CompareTab
          tickers={activeList ? listTickers : [upperTicker, ...compareTickers]}
          years={effectiveYears}
          onTickersChange={(next) => {
            if (activeList) {
              setListTickers(next);
              return;
            }
            setCompareTickers(next.filter((ticker) => ticker !== upperTicker));
          }}
          pinnedTicker={activeList ? null : upperTicker}
          savedListId={activeListId}
        />
      )}

      {/* Sponds tab */}
      {activeTab === "sponds" && !activeList && (
        <SpondsTab ticker={upperTicker} />
      )}

      {/* AI Analysis */}
      {company && !activeList && <CompanyAnalysis ticker={upperTicker} />}

      {/* Sector peers */}
      {peers.length > 0 && !activeList && (
        <div className="pe10-card">
          <nav className="card-section" aria-label={t("sector.same_sector")}>
            <div className="card-section-heading">{t("sector.same_sector")}</div>
            <div className="sector-peers-list">
              {peers.slice(0, 8).map((peer) => (
                <Link
                  key={peer.symbol}
                  href={`/${locale}/${peer.symbol}`}
                  className="sector-peer-link"
                >
                  {peer.symbol}
                  {peer.name && <span className="sector-peer-name">{peer.name}</span>}
                </Link>
              ))}
            </div>
          </nav>
        </div>
      )}

      {!activeList && (
        <ShareButtons
          ticker={upperTicker}
          companyName={fullData?.name}
        />
      )}

      {lookupLimit?.kind === "auth-modal" && !limitModalDismissed && (
        <AuthModal
          message={`${t("quota.limit_reached")} ${lookupLimit.limit ?? ""} ${
            locale === "pt" ? "consultas diárias" : "daily queries"
          }. ${t("quota.create_account")} ${t("quota.to_continue")}`}
          onClose={() => setLimitModalDismissed(true)}
          onSuccess={() => {
            setLimitModalDismissed(true);
            queryClient.invalidateQueries({ queryKey: ["auth-user"] });
            queryClient.invalidateQueries({ queryKey: ["quota"] });
            queryClient.invalidateQueries({ queryKey: ["pe10", upperTicker] });
          }}
        />
      )}
    </div>
  );
}
