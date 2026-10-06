// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, cleanup } from "@testing-library/react";
import { CompareRow, getColumns } from "./CompareTab";
import type { CompareEntry } from "../hooks/useCompareData";
import type { QuoteResult } from "../hooks/usePE10";
import { en } from "../i18n/locales/en";
import type { TranslationKey } from "../i18n";
import { NO_UNAVAILABLE_REASONS } from "../utils/trailingRatios";

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>{children}</a>
  ),
}));

afterEach(cleanup);

const translateEn = (key: TranslationKey) => en[key];

function makeEntry(ticker: string, overrides: Partial<CompareEntry> = {}): CompareEntry {
  return {
    ticker,
    data: { ticker, name: `${ticker} Inc.`, logo: "", marketCap: null } as unknown as QuoteResult,
    recent: null,
    pe: null,
    pfcf: null,
    debtToEarnings: null,
    debtToFcf: null,
    unavailableReasons: NO_UNAVAILABLE_REASONS,
    isLoading: false,
    error: null,
    ...overrides,
  };
}

function renderRow(entry: CompareEntry, isPinned: boolean) {
  const dragIndexRef = { current: null } as React.MutableRefObject<number | null>;
  return render(
    <table>
      <tbody>
        <CompareRow
          entry={entry}
          index={0}
          isPinned={isPinned}
          onRemove={vi.fn()}
          columns={getColumns(7, translateEn)}
          dragIndexRef={dragIndexRef}
          onReorder={vi.fn()}
          totalRows={2}
          startGhost={vi.fn()}
          stopGhost={vi.fn()}
          isAuthenticated={false}
          onRequireAuth={vi.fn()}
        />
      </tbody>
    </table>,
  );
}

describe("CompareRow remove column", () => {
  it("renders the remove button inside an always-visible sticky cell", () => {
    const { container } = renderRow(makeEntry("NVDA"), false);
    const removeCell = container.querySelector("td.compare-remove-col");
    expect(removeCell).not.toBeNull();
    const removeButton = removeCell!.querySelector("button.compare-remove-btn");
    expect(removeButton).not.toBeNull();
    expect(removeButton!.getAttribute("aria-label")).toBe("Remove NVDA");
  });

  it("keeps the sticky remove cell (without a button) on the pinned company's row", () => {
    const { container } = renderRow(makeEntry("DUOL"), true);
    const removeCell = container.querySelector("td.compare-remove-col");
    expect(removeCell).not.toBeNull();
    expect(removeCell!.querySelector("button")).toBeNull();
  });

  it("lets the top row of a saved list be removed like any other", () => {
    // A list has no pinned company, so its first row is not privileged.
    // Losing the anchor company must not be impossible.
    const { container } = renderRow(makeEntry("DEXP4"), false);
    const removeButton = container.querySelector("td.compare-remove-col button.compare-remove-btn");
    expect(removeButton).not.toBeNull();
    expect(removeButton!.getAttribute("aria-label")).toBe("Remove DEXP4");
  });

  it("keeps the sticky remove cell on the error row", () => {
    const { container } = renderRow(
      makeEntry("FAIL", { data: null, error: new Error("boom") }),
      false,
    );
    const removeCell = container.querySelector("td.compare-remove-col");
    expect(removeCell).not.toBeNull();
    expect(removeCell!.querySelector("button.compare-remove-btn")).not.toBeNull();
  });

  it("keeps the sticky remove cell on the loading row", () => {
    const { container } = renderRow(makeEntry("LOAD", { data: null, isLoading: true }), false);
    expect(container.querySelector("td.compare-remove-col")).not.toBeNull();
  });
});

describe("CompareRow debt coverage cells", () => {
  const DEBT_TO_EARNINGS_COLUMN = getColumns(7, translateEn).findIndex(
    (column) => column.key === "debtToEarnings",
  );
  // Two cells precede the data columns: the drag handle and the company.
  const LEADING_CELLS = 2;

  function debtToEarningsCell(container: HTMLElement) {
    return container.querySelectorAll("td")[LEADING_CELLS + DEBT_TO_EARNINGS_COLUMN];
  }

  it("shows the ratio when there is one", () => {
    const { container } = renderRow(makeEntry("NVDA", { debtToEarnings: 2.5 }), false);

    expect(debtToEarningsCell(container).textContent).toBe("2.50");
  });

  it("names a negative average in the cell instead of leaving a bare dash", () => {
    const { container } = renderRow(
      makeEntry("NVDA", {
        unavailableReasons: { ...NO_UNAVAILABLE_REASONS, debtToEarnings: "negative_average" },
      }),
      false,
    );

    const reason = debtToEarningsCell(container).querySelector("span.compare-null-reason");
    expect(reason).not.toBeNull();
    expect(reason!.textContent).toBe(en["fundamentals.unavailable.negative_earnings_short"]);
    expect(reason!.getAttribute("title")).toBe(en["fundamentals.unavailable.negative_earnings"]);
  });

  it("keeps the dash, with the reason on hover, when the history is too short", () => {
    const { container } = renderRow(
      makeEntry("NVDA", {
        unavailableReasons: { ...NO_UNAVAILABLE_REASONS, debtToEarnings: "insufficient_history" },
      }),
      false,
    );

    const blank = debtToEarningsCell(container).querySelector("span.compare-null");
    expect(blank).not.toBeNull();
    expect(blank!.classList.contains("compare-null-reason")).toBe(false);
    expect(blank!.getAttribute("title")).toBe(en["fundamentals.unavailable.insufficient_history"]);
  });

  it("leaves an ordinary blank cell without a hover text", () => {
    const { container } = renderRow(makeEntry("NVDA"), false);

    const blank = debtToEarningsCell(container).querySelector("span.compare-null");
    expect(blank).not.toBeNull();
    expect(blank!.hasAttribute("title")).toBe(false);
  });
});
