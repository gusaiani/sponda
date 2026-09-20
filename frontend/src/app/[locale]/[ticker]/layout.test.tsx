import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

/**
 * `/wp-admin/install.php` is not a company page, but it used to be served
 * as one.
 *
 * The middleware validates the locale segment, but its matcher skips any
 * path containing a dot, so a scanner probing `install.php`, `wp-login.php`
 * or `.env` never reaches it. The App Router then matched the path against
 * `/[locale]/[ticker]` and this layout cast `wp-admin` to SupportedLocale
 * without looking at it, which crashed metadata generation 5,791 times in
 * twenty days and, before that, spent a Django round trip per probe.
 *
 * An unsupported locale is a 404, the same answer the locale layout below
 * it already gives.
 */
const { notFound } = vi.hoisted(() => ({
  notFound: vi.fn(() => {
    throw new Error("NEXT_NOT_FOUND");
  }),
}));

vi.mock("next/navigation", () => ({ notFound }));

import { generateMetadata } from "./layout";

const params = (locale: string, ticker: string) =>
  Promise.resolve({ locale, ticker });

describe("the company layout's metadata", () => {
  beforeEach(() => {
    notFound.mockClear();
    vi.stubGlobal("fetch", vi.fn(async () => ({
      ok: true,
      json: async () => ({ name: "Vulcabras", sector: "Consumer Non-Durables" }),
    })));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("404s on a locale we do not serve", async () => {
    await expect(
      generateMetadata({ children: null, params: params("wp-admin", "install.php") }),
    ).rejects.toThrow("NEXT_NOT_FOUND");

    expect(notFound).toHaveBeenCalled();
  });

  it("never asks Django about a ticker on a path we will not serve", async () => {
    await generateMetadata({
      children: null,
      params: params("wp-admin", "install.php"),
    }).catch(() => undefined);

    expect(fetch).not.toHaveBeenCalled();
  });

  it("still builds metadata for a supported locale", async () => {
    const metadata = await generateMetadata({
      children: null,
      params: params("pt", "vulc3"),
    });

    expect(notFound).not.toHaveBeenCalled();
    expect(metadata.title).toContain("VULC3");
  });
});
