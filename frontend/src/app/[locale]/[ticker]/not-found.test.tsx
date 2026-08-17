// @vitest-environment jsdom
import { describe, it, expect, afterEach } from "vitest";
import { render, cleanup } from "@testing-library/react";
import { LanguageProvider } from "../../../i18n/LanguageContext";
import type { Locale } from "../../../i18n/types";
import { pt } from "../../../i18n/locales/pt";
import { en } from "../../../i18n/locales/en";
import { de } from "../../../i18n/locales/de";
import { zh } from "../../../i18n/locales/zh";
import TickerNotFound from "./not-found";

/**
 * This page used to hardcode its Portuguese and English copy inline, which
 * meant the five other supported locales silently got English. These tests
 * pin that every locale renders its own dictionary.
 */

afterEach(cleanup);

function renderIn(locale: Locale) {
  return render(
    <LanguageProvider initialLocale={locale}>
      <TickerNotFound />
    </LanguageProvider>,
  );
}

describe("TickerNotFound", () => {
  it("renders the Portuguese copy for pt", () => {
    const { container } = renderIn("pt");

    expect(container.textContent).toContain(pt["ticker.not_found_title"]);
    expect(container.textContent).toContain(pt["ticker.not_found_text"]);
  });

  it("renders the English copy for en", () => {
    const { container } = renderIn("en");

    expect(container.textContent).toContain(en["ticker.not_found_title"]);
    expect(container.textContent).toContain(en["ticker.not_found_text"]);
  });

  it("renders German rather than falling back to English", () => {
    const { container } = renderIn("de");

    expect(container.textContent).toContain(de["ticker.not_found_title"]);
    expect(container.textContent).not.toContain(en["ticker.not_found_title"]);
  });

  it("renders Chinese rather than falling back to English", () => {
    const { container } = renderIn("zh");

    expect(container.textContent).toContain(zh["ticker.not_found_title"]);
    expect(container.textContent).not.toContain(en["ticker.not_found_title"]);
  });

  it("links home within the active locale", () => {
    const { container } = renderIn("it");

    const link = container.querySelector("a");
    expect(link?.getAttribute("href")).toBe("/it");
  });
});
